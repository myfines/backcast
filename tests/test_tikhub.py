import unittest
from unittest.mock import patch
import os
import httpx

from services.api.tikhub import TikHubReader, TikHubError, probe_author


class TikHubTests(unittest.TestCase):
    def test_author_id_pagination_and_three_request_ceiling(self):
        calls=[]
        def handler(request):
            calls.append(request)
            self.assertEqual(request.url.host,"api.tikhub.io")
            self.assertEqual(request.headers['Authorization'],'Bearer vendor-test-key')
            self.assertEqual(request.url.params['user_url_token'],'example')
            if request.url.path.endswith('fetch_user_info'):
                data={'url_token':'example','name':'示例作者','answer_count':50}
            else:
                offset=int(request.url.params['offset'])
                data={'data':[{'id':str(offset+1),'content':'<p>一段可实际读取的公开正文。</p>',
                                'author':{'url_token':'example'},'created_time':1609459200}],
                      'paging':{'is_end':False,'next':f'https://www.zhihu.com/api/v4/members/example/answers?offset={offset+1}'}}
            return httpx.Response(200,json={'code':200,'data':data})
        reader=TikHubReader(key='vendor-test-key',transport=httpx.MockTransport(handler))
        result=probe_author(reader,'example',pages=2,limit=3)
        self.assertEqual(len(calls),3)
        self.assertEqual(len(result['items']),2)
        self.assertFalse(result['complete_history'])

    def test_provider_auth_failure_has_no_secret_and_no_retry(self):
        calls=[]
        def handler(request):
            calls.append(request)
            return httpx.Response(401,json={'detail':'vendor-test-key'})
        reader=TikHubReader(key='vendor-test-key',transport=httpx.MockTransport(handler))
        with self.assertRaises(TikHubError) as cm:probe_author(reader,'example')
        self.assertEqual(len(calls),1)
        self.assertNotIn('vendor-test-key',str(cm.exception))

    def test_official_zhihu_secret_is_never_used_as_vendor_key(self):
        with patch.dict(os.environ,{'TIKHUB_API_KEY':'','ZHIHU_ACCESS_SECRET':'official-test-key'}):
            reader=TikHubReader()
            with self.assertRaises(TikHubError) as cm:reader.call('profile','example')
        self.assertEqual(cm.exception.code,'not_configured')

    def test_denied_later_page_keeps_prior_material(self):
        class Reader:
            calls=0
            def call(self,operation,target,offset='0',limit=3):
                self.calls+=1
                if operation=='profile':return {'url_token':target}
                if offset=='0':return {'data':[{'id':'1','excerpt':'只有摘要'}],'paging':{'is_end':False,'next':'https://www.zhihu.com/x?offset=1'}}
                raise TikHubError('access_denied','拒绝')
        with self.assertRaises(TikHubError) as cm:probe_author(Reader(),'example')
        self.assertEqual(len(cm.exception.partial['items']),1)
        self.assertEqual(cm.exception.partial['items'][0]['body_characters'],0)
