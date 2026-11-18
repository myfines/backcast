"""Build and question a named author using source-attributed official results."""
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.api.personas import AuthorDocument, AuthorRequest, build_persona, reply
from services.api.zhihu_official import OfficialClient
from services.api.debate import DebateModel


async def main():
    output = ROOT / '.local/author-persona'
    output.mkdir(parents=True, exist_ok=True)
    os.environ['BACKCAST_DB'] = str(output / 'case.sqlite3')
    seed = ROOT / '.local/debate-case/result.json'
    if seed.exists():
        sources = json.loads(seed.read_text(encoding='utf-8'))['sources']
    else:
        sources = (await OfficialClient().search('解虫 远程办公 协作 沟通', count=5))['items']
    docs = [AuthorDocument(**{k:s[k] for k in ('author_name','url','text','title')}) for s in sources if s.get('author_name')=='解虫']
    if not docs:
        raise RuntimeError('未取得明确署名的作者材料；没有用无作者摘要替代')
    model = DebateModel()
    profile = await build_persona(AuthorRequest(author_name='解虫', documents=docs), model)
    (output/'profile.json').write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding='utf-8')
    answer = await reply(profile['id'], '我认为把任务都写进文档，远程办公就能成为默认模式。你怎么看？', model)
    (output/'reply.json').write_text(json.dumps(answer, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps({'id':profile['id'],'facets':len(profile['facets']),'status':'completed'}, ensure_ascii=True))


if __name__ == '__main__':
    asyncio.run(main())
