import os
import tempfile
import unittest
from unittest.mock import patch

from services.api.debate import SourceQuote, validate_quotes, validate_reply, DebateModel, DebateError
import httpx
from services.api.debate import run_case, get, render_report, qualitative_excerpt
from fastapi import FastAPI
from fastapi.testclient import TestClient
from services.api.debate import router


class DebateTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_create_read_report_and_missing(self):
        app = FastAPI()
        app.include_router(router)
        async def finish(data):
            from services.api.debate import save
            data.update(status='completed', sources=[], turns=[])
            save(data)
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'BACKCAST_DB':tmp+'/case.sqlite3'}), patch('services.api.debate.run_case', side_effect=finish):
            with TestClient(app) as client:
                response = client.post('/api/v1/debates', json={'topic':'远程办公', 'stance':'我倾向远程优先'})
                self.assertEqual(response.status_code, 202)
                debate_id = response.json()['id']
                self.assertEqual(client.get('/api/v1/debates/'+debate_id).json()['status'], 'completed')
                report = client.get('/api/v1/debates/'+debate_id+'/report')
                self.assertEqual(report.status_code, 200)
                self.assertIn('text/html', report.headers['content-type'])
                self.assertEqual(client.get('/api/v1/debates/missing').status_code, 404)
                self.assertEqual(client.post('/api/v1/debates', json={'topic':'a'}).status_code, 422)

    async def test_qualitative_context_excludes_unverified_statistics(self):
        text = '研究显示效率提升13%。我喜欢减少通勤。统计调查显示有优势。新人需要带教。'
        self.assertEqual(qualitative_excerpt(text), '我喜欢减少通勤。新人需要带教。')

    async def test_pipeline_persists_complete_report(self):
        class Search:
            async def search(self, query, count):
                return {'retrieved_at':'2026-11-17', 'items':[
                    {'text':'远程可以节约通勤时间。', 'url':'https://zhihu.com/1','title':'远程','author_name':'甲'},
                    {'text':'新人需要更清晰的沟通。', 'url':'https://zhihu.com/2','title':'沟通','author_name':'乙'}]}
        class Model:
            async def generate(self, system, p):
                quote = {'source_id':'s1','quote':'远程可以节约通勤时间'}
                if 'demo_user_stance' in p:
                    return {'personas':[{'id':i,'name':i,'stance':'条件判断','quotes':[quote]} for i in ['A','B']], 'disagreement':'默认制度'}
                if 'speaker' in p:
                    return {'text':'远程可以节约通勤时间，但默认制度还需要考虑新人的协作需求。我们应如何判断团队已经准备好了？','reply_to_quote':'远程可以节约通勤时间' if p['history'] else '', 'quotes':[quote]}
                return {k:['需要考虑任务条件'] for k in ['agreements','disagreements','next_questions']}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'BACKCAST_DB':tmp+'/case.sqlite3'}):
            result = await run_case({'id':'case','topic':'远程办公','stance':'远程优先'}, Search(), Model())
            self.assertEqual(result['status'], 'completed')
            self.assertEqual(len(get('case')['turns']), 6)
            self.assertIn('AI观点分身', render_report(result))

    async def test_search_failure_is_saved_without_demo_dialogue(self):
        class Search:
            async def search(self, *args, **kwargs):
                raise RuntimeError('sensitive upstream detail')
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'BACKCAST_DB':tmp+'/case.sqlite3'}):
            result = await run_case({'id':'failure','topic':'远程办公','stance':'远程优先'}, Search())
            self.assertEqual(get('failure')['status'], 'failed')
            self.assertEqual(result['turns'], [])
            self.assertNotIn('sensitive', result['error'])

    async def test_invented_source_quote_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_quotes([SourceQuote(source_id="s1", quote="保证所有岗位效率翻倍")],
                            [{"id":"s1","text":"我更喜欢不用通勤的工作。"}])

    async def test_unknown_source_is_rejected(self):
        with self.assertRaises(ValueError):
            validate_quotes([SourceQuote(source_id="fake",quote="我喜欢自由")],[])

    async def test_reply_cannot_strawman_previous_speaker(self):
        with self.assertRaises(ValueError):
            validate_reply("你说所有人都适合远程", "我偏好远程，但新人可能需要现场带教。")
        validate_reply("新人可能需要现场带教", "我偏好远程，但新人可能需要现场带教。")

    async def test_model_uses_real_official_chat_without_openai_key(self):
        def handler(request):
            self.assertEqual(request.url.host,"developer.zhihu.com")
            self.assertEqual(request.url.path,"/v1/chat/completions")
            self.assertEqual(request.headers["Authorization"],"Bearer test-secret")
            return httpx.Response(200,json={"choices":[{"message":{"content":"{\"text\":\"真实响应\"}"}}]})
        result=await DebateModel(secret="test-secret",transport=httpx.MockTransport(handler)).generate("system",{"a":1})
        self.assertEqual(result["text"],"真实响应")

    async def test_bad_model_response_is_not_replaced_with_demo_text(self):
        def handler(request):
            return httpx.Response(200,json={"choices":[{"message":{"content":"不是JSON"}}]})
        with self.assertRaises(DebateError):
            await DebateModel(secret="test-secret",transport=httpx.MockTransport(handler)).generate("system",{})

    async def test_rate_limit_retries_are_bounded(self):
        calls = []
        def handler(request):
            calls.append(1)
            return httpx.Response(429)
        with patch('services.api.debate.asyncio.sleep') as sleep:
            with self.assertRaises(DebateError):
                await DebateModel(secret='test', transport=httpx.MockTransport(handler)).generate('system', {})
        self.assertEqual(len(calls), 3)
        self.assertEqual(sleep.await_count, 2)
