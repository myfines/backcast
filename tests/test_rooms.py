import os
import tempfile
import unittest
from unittest.mock import patch

from services.api.personas import persist
from services.api.rooms import RoomRequest, create_room, read_room, discuss


class RoomTests(unittest.IsolatedAsyncioTestCase):
    async def test_http_harness_and_failure_response_preserve_user_turn(self):
        from fastapi import FastAPI
        from fastapi.testclient import TestClient
        from services.api.rooms import router
        class Model:
            async def generate(self,system,p):
                return {'text':'这是没有来源支持的模拟回答，不能被当作成功发言。','reply_to_quote':p['message'],
                        'quotes':[{'source_id':'fake','quote':'不存在的原文'}]}
        app=FastAPI()
        app.include_router(router)
        with TestClient(app) as client, patch('services.api.rooms.DebateModel',return_value=Model()):
            page=client.get('/api/v1/rooms/playground/ui')
            self.assertEqual(page.status_code,200)
            self.assertIn('新建示例讨论室',page.text)
            created=client.post('/api/v1/rooms',json={'persona_id':'author','topic':'远程办公','council':False})
            self.assertEqual(created.status_code,201)
            rid=created.json()['id']
            failed=client.post('/api/v1/rooms/'+rid+'/messages',json={'message':'我倾向远程优先。'})
            self.assertEqual(failed.status_code,502)
            self.assertTrue(failed.json()['detail']['partial_results_saved'])
            saved=client.get('/api/v1/rooms/'+rid).json()
            self.assertEqual(saved['status'],'failed')
            self.assertEqual(len(saved['turns']),1)
            self.assertEqual(client.get('/api/v1/rooms/'+rid+'/report').status_code,200)
            self.assertEqual(client.post('/api/v1/rooms/'+rid+'/messages',json={'message':'嗯'}).status_code,422)

    async def asyncSetUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.env=patch.dict(os.environ, {'BACKCAST_DB':self.tmp.name+'/case.sqlite3'})
        self.env.start()
        persist({'id':'author','author_name':'甲','label':'甲 · AI分身，非本人','facets':[], 'unknowns':[],
                 'documents':[{'id':'p1','text':'远程需要文档沟通。','url':'https://zhihu.com/1'}]})

    async def asyncTearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    async def test_conversation_remembers_previous_turn_and_adds_council(self):
        seen=[]
        class Model:
            async def generate(self, system, p):
                seen.append(p)
                if p['task']=='council':
                    return {'members':[{'role':r,'text':'我们应该先观察任务是否能被清楚描述，再选择工作方式。'} for r in ['实践派','澄清者']]}
                return {'text':'我理解你重视自由，但先判断任务是否写清楚，才好谈远程默认。',
                        'reply_to_quote':p['message'], 'quotes':[{'source_id':'p1','quote':'远程需要文档沟通'}]}
        room=create_room(RoomRequest(persona_id='author',topic='远程办公',council=True))
        first=await discuss(room['id'],'我支持默认远程办公。',Model())
        second=await discuss(room['id'],'如果先做试点，你愿意改变默认制度吗？',Model())
        self.assertEqual(len(second['turns']), 8)
        self.assertEqual(second['turns'][0]['role'],'user')
        self.assertTrue(any('我支持默认远程办公' in str(p.get('history')) for p in seen if p['task']=='reply' and p['message'].startswith('如果')))
        self.assertEqual(read_room(room['id'])['status'],'ready')
        self.assertEqual(first['turns'][2]['kind'],'fictional_council')

    async def test_fabricated_reply_anchor_is_rejected_and_failure_saved(self):
        class Model:
            async def generate(self,system,p):
                return {'text':'你说所有岗位都适合远程，这显然不合理，所以应该坐班。','reply_to_quote':'所有岗位都适合远程',
                        'quotes':[{'source_id':'p1','quote':'远程需要文档沟通'}]}
        room=create_room(RoomRequest(persona_id='author',topic='远程办公'))
        result=await discuss(room['id'],'我偏好远程，但新人可以现场带教。',Model())
        self.assertEqual(result['status'],'failed')
        self.assertEqual(len(result['turns']),1)
        self.assertEqual(result['turns'][0]['role'],'user')

    async def test_busy_room_rejects_concurrent_post(self):
        from services.api.rooms import save_room
        from fastapi import HTTPException
        room=create_room(RoomRequest(persona_id='author',topic='远程办公'))
        room['status']='generating'
        save_room(room)
        with self.assertRaises(HTTPException) as error:
            await discuss(room['id'],'我想再问一个问题。')
        self.assertEqual(error.exception.status_code,409)
