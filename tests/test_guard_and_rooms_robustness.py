import asyncio
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

from services.api import guard
from services.api.personas import persist
from services.api.rooms import (
    INTERRUPTED, RoomRequest, STALE_SECONDS, create_room, discuss, read_room, recover_interrupted, router, save_room,
)


class GuardTests(unittest.TestCase):
    def setUp(self):
        guard.limiter.reset()
        guard.reset_model_state()

    def test_window_limiter_blocks_then_recovers(self):
        lim = guard.WindowLimiter()
        self.assertIsNone(lim.check('a', 2, 100, now=0))
        self.assertIsNone(lim.check('a', 2, 100, now=1))
        wait = lim.check('a', 2, 100, now=2)
        self.assertGreaterEqual(wait, 98)
        self.assertIsNone(lim.check('b', 2, 100, now=2))  # other clients are unaffected
        self.assertIsNone(lim.check('a', 2, 100, now=101))  # the oldest hit expired
        self.assertIsNone(lim.check('c', 0, 100, now=0))  # 0 disables the limit

    def test_model_slots_are_spaced_across_all_callers(self):
        with patch.dict(os.environ, {'MODEL_MIN_GAP_SECONDS': '25', 'MODEL_MAX_QUEUE_SECONDS': '60'}):
            self.assertEqual(guard.reserve_model_slot(now=1000), 0)
            self.assertAlmostEqual(guard.reserve_model_slot(now=1001), 24)  # second caller waits for the gap
            self.assertAlmostEqual(guard.reserve_model_slot(now=1002), 48)
            with self.assertRaises(guard.ModelBusy):  # would wait 72s > 60s: say "busy" instead of queueing
                guard.reserve_model_slot(now=1003)

    def test_daily_budget_stops_further_calls(self):
        with patch.dict(os.environ, {'MODEL_DAILY_BUDGET': '2', 'MODEL_MIN_GAP_SECONDS': '0'}):
            guard.reserve_model_slot(now=1)
            guard.reserve_model_slot(now=2)
            with self.assertRaisesRegex(guard.ModelBusy, '额度'):
                guard.reserve_model_slot(now=3)

    def test_routes_return_429_with_retry_after(self):
        with patch.dict(os.environ, {'RATE_LIMIT_CREATE_PER_HOUR': '2'}):
            app = FastAPI()
            app.include_router(router)
            with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'BACKCAST_DB': tmp + '/g.sqlite3'}):
                persist({'id': 'author', 'author_name': '甲', 'label': '甲 · AI分身，非本人', 'facets': [], 'unknowns': [], 'documents': []})
                client = TestClient(app)
                body = {'persona_id': 'author', 'topic': '远程办公', 'council': False}
                self.assertEqual(client.post('/api/v1/rooms', json=body).status_code, 201)
                self.assertEqual(client.post('/api/v1/rooms', json=body).status_code, 201)
                third = client.post('/api/v1/rooms', json=body)
                self.assertEqual(third.status_code, 429)
                self.assertIn('Retry-After', third.headers)

    def test_client_key_uses_forwarded_for_only_when_trusted(self):
        class Req:
            client = type('C', (), {'host': '10.0.0.1'})()
            headers = {'x-forwarded-for': '203.0.113.9, 10.0.0.1'}
        self.assertEqual(guard.client_key(Req()), '10.0.0.1')
        with patch.dict(os.environ, {'TRUST_PROXY': '1'}):
            self.assertEqual(guard.client_key(Req()), '203.0.113.9')

    def test_persona_creation_needs_admin_token_when_configured(self):
        from services.api.personas import router as persona_router
        app = FastAPI()
        app.include_router(persona_router)
        body = {'author_name': '甲', 'documents': [{'author_name': '甲', 'url': 'https://zhuanlan.zhihu.com/p/1', 'text': '这是一段足够长的公开文章内容。'}]}
        client = TestClient(app)
        with patch.dict(os.environ, {'PERSONA_ADMIN_TOKEN': 'secret-admin'}):
            self.assertEqual(client.post('/api/v1/personas', json=body).status_code, 403)
            self.assertEqual(client.post('/api/v1/personas', json=body, headers={'X-Admin-Token': 'wrong'}).status_code, 403)


class RoomRobustnessTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        guard.limiter.reset()
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'BACKCAST_DB': self.tmp.name + '/case.sqlite3'})
        self.env.start()
        persist({'id': 'author', 'author_name': '甲', 'label': '甲 · AI分身，非本人', 'facets': [], 'unknowns': [],
                 'documents': [{'id': 'p1', 'text': '远程需要文档沟通。', 'url': 'https://zhihu.com/1'}]})

    async def asyncTearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def good_reply(self, p):
        return {'text': '我理解你重视自由，但先判断任务是否写清楚，才好谈远程默认。', 'reply_to_quote': p['message'],
                'quotes': [{'source_id': 'p1', 'quote': '远程需要文档沟通'}]}

    async def test_guard_failure_is_retried_once_with_the_reason(self):
        calls = []
        outer = self

        class Model:
            async def generate(self, system, p):
                calls.append(p)
                if len(calls) == 1:
                    return {'text': '没有来源的回答不能通过校验，所以这一次会被拒绝。', 'reply_to_quote': p['message'],
                            'quotes': [{'source_id': 'p1', 'quote': '原文里没有这句话'}]}
                return outer.good_reply(p)

        room = create_room(RoomRequest(persona_id='author', topic='远程办公'))
        result = await discuss(room['id'], '我支持默认远程办公。', Model())
        self.assertEqual(result['status'], 'ready')
        self.assertEqual(len(calls), 2)
        self.assertIn('格式纠正', calls[1])
        self.assertNotIn('格式纠正', calls[0])

    async def test_model_errors_are_not_retried(self):
        from services.api.debate import DebateError
        calls = []

        class Model:
            async def generate(self, system, p):
                calls.append(p)
                raise DebateError('缺少知乎官方凭证')

        room = create_room(RoomRequest(persona_id='author', topic='远程办公'))
        result = await discuss(room['id'], '我支持默认远程办公。', Model())
        self.assertEqual(result['status'], 'failed')
        self.assertEqual(len(calls), 1)
        self.assertEqual(result['error'], '缺少知乎官方凭证')

    async def test_failed_rounds_do_not_use_up_the_allowance(self):
        from services.api.debate import DebateError

        class Failing:
            async def generate(self, system, p):
                raise DebateError('缺少知乎官方凭证')

        room = create_room(RoomRequest(persona_id='author', topic='远程办公'))
        for _ in range(13):
            await discuss(room['id'], '我支持默认远程办公。', Failing())
        self.assertEqual(read_room(room['id'])['status'], 'failed')
        outer = self

        class Ok:
            async def generate(self, system, p):
                return outer.good_reply(p)

        again = await discuss(room['id'], '我支持默认远程办公。', Ok())  # still allowed: nothing was answered
        self.assertEqual(again['status'], 'ready')

    async def test_cancelled_request_releases_the_room(self):
        class Slow:
            async def generate(self, system, p):
                raise asyncio.CancelledError()

        room = create_room(RoomRequest(persona_id='author', topic='远程办公'))
        with self.assertRaises(asyncio.CancelledError):
            await discuss(room['id'], '我支持默认远程办公。', Slow())
        saved = read_room(room['id'])
        self.assertEqual(saved['status'], 'failed')
        self.assertEqual(saved['error'], INTERRUPTED)
        self.assertEqual(len(saved['turns']), 1)  # the user's turn is kept

    async def test_stale_generating_room_is_shown_as_failed_and_can_be_used_again(self):
        room = create_room(RoomRequest(persona_id='author', topic='远程办公'))
        old = (datetime.now(timezone.utc) - timedelta(seconds=STALE_SECONDS + 60)).isoformat()
        save_room({**room, 'status': 'generating', 'generating_since': old})
        shown = read_room(room['id'])
        self.assertEqual(shown['status'], 'failed')
        self.assertEqual(shown['error'], INTERRUPTED)
        outer = self

        class Ok:
            async def generate(self, system, p):
                return outer.good_reply(p)

        self.assertEqual((await discuss(room['id'], '我支持默认远程办公。', Ok()))['status'], 'ready')

    async def test_recent_generating_room_is_left_alone_and_startup_recovers_it(self):
        room = create_room(RoomRequest(persona_id='author', topic='远程办公'))
        save_room({**room, 'status': 'generating', 'generating_since': datetime.now(timezone.utc).isoformat()})
        self.assertEqual(read_room(room['id'])['status'], 'generating')
        recover_interrupted()  # a restart: nothing can still be generating
        self.assertEqual(read_room(room['id'])['status'], 'failed')


class SummaryTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        guard.limiter.reset()
        self.tmp = tempfile.TemporaryDirectory()
        self.env = patch.dict(os.environ, {'BACKCAST_DB': self.tmp.name + '/case.sqlite3'})
        self.env.start()
        persist({'id': 'author', 'author_name': '甲', 'label': '甲 · AI分身，非本人', 'facets': [], 'unknowns': [],
                 'documents': [{'id': 'p1', 'text': '远程需要文档沟通。', 'url': 'https://zhihu.com/1'}]})
        outer = self

        class Ok:
            async def generate(self, system, p):
                return {'text': '我理解你重视自由，但先判断任务是否写清楚，才好谈远程默认。', 'reply_to_quote': p['message'],
                        'quotes': [{'source_id': 'p1', 'quote': '远程需要文档沟通'}]}

        room = create_room(RoomRequest(persona_id='author', topic='远程办公'))
        self.room = await discuss(room['id'], '我支持默认远程办公，也愿意先写文档。', Ok())

    async def asyncTearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def summary_json(self, quote='先判断任务是否写清楚'):
        return {'agreements': [{'text': '双方都认为文档是远程协作的基础。', 'quotes': [{'turn': 1, 'quote': quote}]}],
                'factual_disagreements': [], 'value_disagreements': [], 'concessions': [],
                'open_questions': ['哪些岗位的任务可以被清楚地写成文档？']}

    async def test_summary_is_saved_and_every_quote_exists_in_the_cited_turn(self):
        from services.api.rooms import summarize_room

        class Model:
            def __init__(self, data): self.data = data
            async def generate(self, system, p):
                assert p['task'] == 'summary'
                return self.data

        out = await summarize_room(self.room['id'], Model(self.summary_json()))
        self.assertIn('不判断谁赢', out['note'])
        self.assertEqual(read_room(self.room['id'])['summary']['agreements'][0]['quotes'][0]['turn'], 1)

    async def test_invented_quote_is_rejected_after_one_retry(self):
        from services.api.rooms import summarize_room
        from services.api.debate import DebateError
        calls = []

        class Model:
            async def generate(self, system, p):
                calls.append(p)
                return {'agreements': [{'text': '双方都同意坐班更好。', 'quotes': [{'turn': 1, 'quote': '这句话没有人说过'}]}]}

        with self.assertRaises(DebateError):
            await summarize_room(self.room['id'], Model())
        self.assertEqual(len(calls), 2)
        self.assertIn('格式纠正', calls[1])
        self.assertNotIn('summary', read_room(self.room['id']))

    async def test_summary_needs_an_answered_round(self):
        from fastapi import HTTPException
        from services.api.rooms import summarize_room
        empty = create_room(RoomRequest(persona_id='author', topic='远程办公'))
        with self.assertRaises(HTTPException) as e:
            await summarize_room(empty['id'], object())
        self.assertEqual(e.exception.status_code, 409)

    async def test_summary_http_failure_is_502_not_a_made_up_summary(self):
        app = FastAPI()
        app.include_router(router)
        # Make sure this never reaches the real model, whatever is configured on the developer's machine.
        with patch.dict(os.environ, {'ZHIHU_ACCESS_SECRET': '', 'ZHIHU_CREDENTIAL_FILE': self.tmp.name + '/none.env'}), TestClient(app) as client:
            r = client.post('/api/v1/rooms/' + self.room['id'] + '/summary')
            self.assertEqual(r.status_code, 502)
            self.assertIn('缺少知乎官方凭证', r.json()['detail'])
            self.assertNotIn('summary', client.get('/api/v1/rooms/' + self.room['id']).json())


if __name__ == '__main__':
    unittest.main()
