import os
import tempfile
import unittest
from unittest.mock import patch

from services.api.personas import AuthorDocument, AuthorRequest, build_persona, retrieve, reply


class PersonaTests(unittest.IsolatedAsyncioTestCase):
    async def test_named_author_debate_is_bound_to_author_sources(self):
        from services.api.personas import persist
        from services.api.debate import run_case
        class Model:
            def __init__(self, wrong): self.wrong=wrong
            async def generate(self, system, p):
                if 'speaker' not in p:
                    return {k:['讨论实际条件'] for k in ['agreements','disagreements','next_questions']}
                source='p1' if p['speaker']=='B' and not self.wrong else 's1'
                return {'text':'远程需要文档沟通，但是否作为默认模式仍要看团队的实际协调需求。你会如何判断这一点？',
                        'reply_to_quote':'远程需要文档沟通' if p['history'] else '',
                        'quotes':[{'source_id':source,'quote':'远程需要文档沟通'}]}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'BACKCAST_DB':tmp+'/case.sqlite3'}):
            persist({'id':'author','author_name':'甲','label':'甲 · AI分身，非本人','created_at':'2026-11-17',
                     'facets':[],'unknowns':[],'documents':[{'id':'p1','text':'远程需要文档沟通。','url':'https://zhihu.com/1','title':'文档','author_name':'甲'}]})
            for wrong in (False, True):
                data={'id':str(wrong),'topic':'远程办公','stance':'远程优先','opponent_persona_id':'author',
                      'sources':[{'id':sid,'text':'远程需要文档沟通。','url':'https://zhihu.com/'+sid} for sid in ['s1','s2']],
                      'plan':{'personas':[{'id':i,'name':i,'stance':'看条件','quotes':[]} for i in ['A','B']]}}
                result=await run_case(data,model=Model(wrong))
                self.assertEqual(result['status'],'failed' if wrong else 'completed')
                if not wrong:
                    self.assertEqual(result['plan']['personas'][1]['author_persona_id'],'author')
                    self.assertTrue(all(t['quotes'][0]['source_id']=='p1' for t in result['turns'] if t['speaker']=='B'))

    async def test_different_authors_cannot_be_merged(self):
        with self.assertRaises(ValueError):
            AuthorRequest(author_name='甲', documents=[AuthorDocument(author_name='乙', url='https://zhihu.com/1', text='这是乙的观点和表达。')])

    async def test_retrieval_uses_only_this_personas_memory(self):
        docs=[{'id':'p1','text':'远程工作需要文档沟通'}, {'id':'p2','text':'美食与旅游'}]
        self.assertEqual(retrieve({'documents':docs}, '远程工作', limit=1)[0]['id'], 'p1')

    async def test_retrieval_finds_relevant_material_beyond_document_start(self):
        doc={'id':'p1','text':'旅游美食。'*600+'远程工作需要文档沟通。'}
        found=retrieve({'documents':[doc]}, '远程工作')[0]
        self.assertIn('远程工作',found['text'])
        self.assertLessEqual(len(found['text']), 1400)

    async def test_profile_and_reply_are_persisted_and_source_checked(self):
        class Model:
            async def generate(self, system, payload):
                q={'source_id':'p1','quote':'远程工作需要文档沟通'}
                if payload['task']=='profile':
                    return {'facets':[{'kind':'principle','description':'重视沟通条件','quotes':[q]}], 'unknowns':['其他议题立场未知']}
                return {'text':'我会先看团队能否把任务和标准写清楚，再讨论是否远程。','quotes':[q]}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'BACKCAST_DB':tmp+'/case.sqlite3'}):
            request=AuthorRequest(author_name='甲', documents=[AuthorDocument(author_name='甲',url='https://zhihu.com/1',text='远程工作需要文档沟通。')])
            profile=await build_persona(request, Model())
            result=await reply(profile['id'], '你支持远程吗？', Model())
            self.assertEqual(result['persona_id'], profile['id'])
            self.assertEqual(result['quotes'][0]['source_id'], 'p1')

    async def test_fabricated_profile_evidence_is_rejected(self):
        class Model:
            async def generate(self, system, payload):
                return {'facets':[{'kind':'value','description':'自由优先','quotes':[{'source_id':'p1','quote':'我最看重自由'}]}], 'unknowns':[]}
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {'BACKCAST_DB':tmp+'/case.sqlite3'}):
            with self.assertRaises(ValueError):
                await build_persona(AuthorRequest(author_name='甲', documents=[AuthorDocument(author_name='甲',url='https://zhihu.com/1',text='远程工作需要文档沟通。')]), Model())
