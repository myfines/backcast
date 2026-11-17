"""Author-scoped source memory and evidence-linked persona cards.

Design references: tinasheosewe/persona-chatbot (MIT), mindverse/Second-Me
(Apache-2.0). Context block renderer adapted under MIT; see persona_context.py.
"""
import json
import re
from uuid import uuid4
from urllib.parse import urlparse

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field, field_validator, model_validator

from . import store
from .debate import DebateModel, DebateError, SYSTEM, SourceQuote, validate_quotes, validate_reply
from .persona_context import render_context_blocks


class AuthorDocument(BaseModel):
    author_name: str = Field(min_length=1, max_length=100)
    url: str = Field(max_length=2000)
    text: str = Field(min_length=10, max_length=30000)
    title: str = Field(default='', max_length=300)
    published_at: str | None = None
    is_excerpt: bool = True

    @field_validator('url')
    @classmethod
    def public_zhihu_url(cls, value):
        p = urlparse(value)
        if p.scheme != 'https' or not p.hostname or not (p.hostname == 'zhihu.com' or p.hostname.endswith('.zhihu.com')) or p.username or p.password:
            raise ValueError('需要公开知乎 HTTPS 来源链接')
        return value


class AuthorRequest(BaseModel):
    author_name: str = Field(min_length=1, max_length=100)
    documents: list[AuthorDocument] = Field(min_length=1, max_length=30)

    @model_validator(mode='after')
    def same_author(self):
        if any(d.author_name.strip() != self.author_name.strip() for d in self.documents):
            raise ValueError('只能导入同一作者材料，不能合并不同作者')
        if len({d.url for d in self.documents}) != len(self.documents):
            raise ValueError('来源链接不能重复')
        return self


def persist(persona):
    with store.db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS personas (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        c.execute('INSERT OR REPLACE INTO personas VALUES (?,?)', (persona['id'], json.dumps(persona, ensure_ascii=False)))


def load(persona_id):
    with store.db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS personas (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        row = c.execute('SELECT data FROM personas WHERE id=?', (persona_id,)).fetchone()
    if not row:
        raise HTTPException(404, '作者分身不存在')
    return json.loads(row['data'])


def retrieve(persona, query, limit=3):
    # Chinese bigrams + words avoid an extra embedding service in the local MVP.
    def terms(text):
        return set(re.findall(r'[a-zA-Z]{2,}', text.lower()) + re.findall(r'(?=([\u4e00-\u9fff]{2}))', text))
    q = terms(query)
    candidates = []
    for d in persona['documents']:
        chunks = [(start, d['text'][start:start+1400]) for start in range(0, len(d['text']), 1200)]
        start, text = max(chunks, key=lambda pair: len(q & terms(pair[1])))
        candidates.append(dict(d, text=text, excerpt_start=start))
    return sorted(candidates, key=lambda d: len(q & terms(d['text'])), reverse=True)[:limit]


async def build_persona(body, model=None):
    docs = [dict(d.model_dump(), id='p'+str(i+1)) for i, d in enumerate(body.documents)]
    # Bound context; complete imports are retained for later author-scoped retrieval.
    context = [{**d, 'text':d['text'][:1800]} for d in docs[:12]]
    result = await (model or DebateModel()).generate(SYSTEM + '''\n根据单一作者材料构建可复用画像卡。
只提取有直接原文支持的观点、价值取舍、判断习惯、表达风格。kind可为view/value/principle/style。
不猜隐私人格、人生经历或未谈过的议题；不要把一次表达写成永恒人格。description使用“这些材料中表现为”。
返回JSON {facets:[{kind,description,quotes:[{source_id,quote}]}],unknowns:[字符串]}。
最多六个facet，每个只引一小段原文。unknowns列出无法推断的部分。''',
        {'task':'profile','instruction':'仅返回以下结构的严格JSON，不要Markdown或解释。提取最多四个有原文支持的观点、价值、判断习惯或表达风格。quotes必须逐字引用documents。',
         'output_schema':{'facets':[{'kind':'view/value/principle/style','description':'材料支持的简短画像','quotes':[{'source_id':'p1','quote':'原文中的连续短句'}]}],'unknowns':['材料无法推断的部分']},
         'author_name':body.author_name,'documents':context})
    if not isinstance(result.get('facets'), list) or not 1 <= len(result['facets']) <= 8:
        raise ValueError('模型未返回有效画像卡')
    for facet in result['facets']:
        if facet.get('kind') not in ('view','value','principle','style') or not isinstance(facet.get('description'), str) or not facet.get('quotes'):
            raise ValueError('画像维度必须有类型、描述和原文依据')
        validate_quotes([SourceQuote(**q) for q in facet['quotes']], context)
    if not isinstance(result.get('unknowns'), list) or not all(isinstance(x, str) for x in result['unknowns']):
        raise ValueError('画像需要标注未知范围')
    persona = dict(id=uuid4().hex, author_name=body.author_name, label=body.author_name+' · AI分身，非本人',
        facets=result['facets'], unknowns=result['unknowns'], documents=docs,
        coverage={'documents':len(docs),'profiled_documents':len(context),'complete_personality':False,
                  'author_identity_verified':False,'input_authorship':'导入者标注，未独立核验'},
        created_at=store.utcnow())
    persist(persona)
    return persona


async def reply(persona_id, message, model=None, history=None):
    persona = load(persona_id)
    docs = retrieve(persona, message)
    context = [{**d,'text':d['text'][:2400]} for d in docs]
    result = await (model or DebateModel()).generate(SYSTEM + '''\n你模拟指定作者的公开表达和判断习惯，与用户讨论。
资料不足的议题明确承认未知，不自动赞同用户，不编造个人经历。不要自称真人。
不要编造某月必然失败等具体后果或时间。用户未说“只靠口头沟通”就不能当作其方案。
条件被用户补足时可以接受方案；追问应推进讨论，不要为了维持反对身份不断追加无关门槛。
如果先前发言没有依据或误读用户，请直接承认并纠正，不要改口称提醒来维护面子。
返回JSON {text:约一百五十字的回答,quotes:[{source_id,quote}]}。至少一段逐字来源。
引用是作者说过的依据，不等于其陈述已经被证实。''',
        {'task':'reply','instruction':'只返回严格JSON，不要Markdown：{"text":"模拟作者的一百五十字回答","quotes":[{"source_id":"p1","quote":"资料中的连续原文"}]}。不能冒充真人。',
         'author_name':persona['author_name'],
         'history': (history or [])[-12:],
         'required_output': ({'text':'回应当前追问','reply_to_quote':'逐字摘录当前message的四至六十字','quotes':[{'source_id':'p1','quote':'来源中的连续原文'}]} if history is not None else None),
         'conversation_instruction': ('reply_to_quote必须逐字摘录当前message中至少四字；根据历史回答本次追问，不要重复开场。text中须回应该观点，不得强造用户前提。' if history is not None else ''),
         'context':render_context_blocks({
             'interpretation':[f["kind"]+': '+f['description'] for f in persona['facets']],
             'disambiguation':persona['unknowns'],
             'textual_evidence':[d['id']+' '+d['text'] for d in context]}),
         'message':message})
    if not isinstance(result.get('text'), str) or not 10 <= len(result['text']) <= 1800 or not result.get('quotes'):
        raise ValueError('回答缺少正文或来源')
    validate_quotes([SourceQuote(**q) for q in result['quotes']], context)
    if history is not None:
        validate_reply(result.get('reply_to_quote'), message)
    result.update(persona_id=persona_id, label=persona['label'], generated_at=store.utcnow())
    with store.db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS persona_interactions (id TEXT PRIMARY KEY, persona_id TEXT, data TEXT NOT NULL)')
        c.execute('INSERT INTO persona_interactions VALUES (?,?,?)', (uuid4().hex, persona_id, json.dumps({'message':message,'reply':result},ensure_ascii=False)))
    return result


class ChatRequest(BaseModel):
    message: str = Field(min_length=2, max_length=1500)


router = APIRouter(prefix='/api/v1/personas', tags=['author personas'])


@router.post('')
async def create(body: AuthorRequest):
    try:
        return await build_persona(body)
    except (DebateError, ValueError) as error:
        raise HTTPException(502, str(error)) from error


@router.get('/{persona_id}')
def read(persona_id: str):
    return load(persona_id)


@router.post('/{persona_id}/chat')
async def chat(persona_id: str, body: ChatRequest):
    try:
        return await reply(persona_id, body.message)
    except (DebateError, ValueError) as error:
        raise HTTPException(502, str(error)) from error
