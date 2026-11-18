"""Small persistent discussion rooms: one author avatar plus an optional AI panel."""
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import guard, store
from .debate import DebateModel, DebateError, SYSTEM
from .personas import load, reply

MAX_ROUNDS = 12
# A room still "generating" after this long was interrupted (restart, dropped connection, crash).
STALE_SECONDS = 600
INTERRUPTED = '上一次生成被中断（服务重启或连接断开），已保留已有对话，可以重新发送。'


class RoomRequest(BaseModel):
    persona_id: str = Field(min_length=1, max_length=64)
    topic: str = Field(min_length=4, max_length=160)
    council: bool = False


class RoomMessage(BaseModel):
    message: str = Field(min_length=4, max_length=1500)


class DemoRequest(BaseModel):
    council: bool = True


def _ensure(c):
    c.execute('CREATE TABLE IF NOT EXISTS discussion_rooms (id TEXT PRIMARY KEY, data TEXT NOT NULL)')


def save_room(room):
    with store.db() as c:
        _ensure(c)
        c.execute('INSERT OR REPLACE INTO discussion_rooms VALUES (?,?)', (room['id'], json.dumps(room,ensure_ascii=False)))


def _age_seconds(room, now=None):
    stamp = room.get('generating_since') or room.get('updated_at') or room.get('created_at')
    try:
        then = datetime.fromisoformat(stamp)
    except (TypeError, ValueError):
        return 0.0
    if then.tzinfo is None:
        then = then.replace(tzinfo=timezone.utc)
    return ((now or datetime.now(timezone.utc)) - then).total_seconds()


def _interrupt(room):
    room.pop('generating_since', None)
    room.update(status='failed', error=INTERRUPTED, updated_at=store.utcnow())
    return room


def read_room(room_id):
    with store.db() as c:
        _ensure(c)
        row=c.execute('SELECT data FROM discussion_rooms WHERE id=?',(room_id,)).fetchone()
    if not row:
        raise HTTPException(404,'讨论室不存在')
    room=json.loads(row['data'])
    if room['status']=='generating' and _age_seconds(room)>STALE_SECONDS:
        # Never leave a reader looking at a spinner that will not finish.
        save_room(_interrupt(room))
    return room


def recover_interrupted():
    """At startup nothing can still be generating: mark those rooms failed instead of leaving them locked."""
    with store.db() as c:
        _ensure(c)
        rows=c.execute('SELECT data FROM discussion_rooms').fetchall()
    for row in rows:
        room=json.loads(row['data'])
        if room.get('status')=='generating':
            save_room(_interrupt(room))


def create_room(body):
    persona=load(body.persona_id)
    room=dict(id=uuid4().hex,**body.model_dump(),author_label=persona['label'],status='ready',
              turns=[],created_at=store.utcnow(),user_role_note='用户发言可能由真人或开发者扮演，演示记录会明确标注')
    save_room(room)
    return room


def answered_rounds(room):
    """Rounds that got an answer. A round that failed does not use up the room's allowance."""
    return sum(t.get('kind')=='author_avatar' for t in room['turns'])


def claim_room(room_id):
    # Serialize concurrent posts in SQLite, including posts from separate workers.
    with store.db() as c:
        _ensure(c)
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT data FROM discussion_rooms WHERE id=?',(room_id,)).fetchone()
        if not row:
            raise HTTPException(404,'讨论室不存在')
        room=json.loads(row['data'])
        if room['status']=='generating' and _age_seconds(room)<=STALE_SECONDS:
            raise HTTPException(409,'上一条回应仍在生成，请先等待')
        if answered_rounds(room) >= MAX_ROUNDS:
            raise HTTPException(409,'本场已达十二次提问上限，请新建讨论室')
        room.update(status='generating',generating_since=store.utcnow())
        room.pop('error',None)
        c.execute('UPDATE discussion_rooms SET data=? WHERE id=?',(json.dumps(room,ensure_ascii=False),room_id))
    return room


async def reply_with_retry(persona_id, message, model, history):
    """The fidelity guards (verbatim quotes, real reply anchor) reject some model outputs.
    Retry once, telling the model what was wrong; a model or network error is not retried."""
    correction=None
    for attempt in range(2):
        try:
            return await reply(persona_id,message,model,history=history,correction=correction)
        except ValueError as error:
            if attempt==1:
                raise
            correction=str(error)


async def discuss(room_id, message, model=None):
    room=claim_room(room_id)
    model=model or DebateModel()
    history=[{'role':t['role'],'name':t['name'],'text':t['text']} for t in room['turns']][-12:]
    room['turns'].append(dict(role='user',kind='user',name='用户',text=message,created_at=store.utcnow()))
    save_room(room)
    try:
        answer=await reply_with_retry(room['persona_id'],message,model,history)
        room['turns'].append(dict(answer,role='assistant',kind='author_avatar',name=room['author_label']))
        save_room(room)
        if room['council']:
            result=await model.generate(SYSTEM+'''\n你扮演两位虚构AI讨论参与者：实践派和澄清者。
实践派提出可操作的试点；澄清者指出真实分歧并提出追问。只推演已有对话，不添加外部事实。
不能判输赢，不能凭空设定对方承诺，不声称代表任何真人。每人约八十字。''',
                {'task':'council','instruction':'仅返回严格JSON：{"members":[{"role":"实践派","text":"建议"},{"role":"澄清者","text":"追问"}]}。内容必须针对本次对话。',
                 'topic':room['topic'],'history':[{'name':t['name'],'text':t['text']} for t in room['turns']][-12:]})
            members=result.get('members')
            if not isinstance(members,list) or len(members)!=2 or {m.get('role') for m in members if isinstance(m,dict)}!={'实践派','澄清者'}:
                raise ValueError('辩论团返回格式无效')
            for member in members:
                if not isinstance(member.get('text'),str) or not 10<=len(member['text'])<=1200:
                    raise ValueError('辩论团发言无效')
            room['turns'].extend(dict(role='assistant',kind='fictional_council',name=m['role']+' · 虚构AI角色',text=m['text'],created_at=store.utcnow()) for m in members)
        room.pop('generating_since',None)
        room.update(status='ready',updated_at=store.utcnow())
    except asyncio.CancelledError:
        # The client went away mid-generation: keep the conversation and release the room.
        save_room(_interrupt(room))
        raise
    except Exception as error:
        room.pop('generating_since',None)
        room.update(status='failed',error=str(error) if isinstance(error,(DebateError,ValueError)) else '回应生成失败，已保留已有对话')
    save_room(room)
    return room


# ---- discussion summary -------------------------------------------------------

class SummaryQuote(BaseModel):
    turn: int = Field(ge=0, description='Index into room.turns')
    quote: str = Field(min_length=4, max_length=300)


class SummaryItem(BaseModel):
    text: str = Field(min_length=4, max_length=300)
    quotes: list[SummaryQuote] = Field(min_length=1, max_length=3)


class RoomSummary(BaseModel):
    agreements: list[SummaryItem] = Field(default=[], max_length=5)
    factual_disagreements: list[SummaryItem] = Field(default=[], max_length=5)
    value_disagreements: list[SummaryItem] = Field(default=[], max_length=5)
    concessions: list[SummaryItem] = Field(default=[], max_length=5)
    open_questions: list[str] = Field(default=[], max_length=5)


class RoomSummaryOut(RoomSummary):
    generated_at: str
    note: str
    turn_count: int


SUMMARY_NOTE = 'AI 生成的总结，可能遗漏或曲解；每一条都附有对话中的原句，请对照核对。总结不判断谁赢。'


def validate_summary(summary, turns):
    """Every cited sentence must exist verbatim in the turn it points at."""
    for group in (summary.agreements, summary.factual_disagreements, summary.value_disagreements, summary.concessions):
        for item in group:
            for q in item.quotes:
                if q.turn >= len(turns) or q.quote not in turns[q.turn]['text']:
                    raise ValueError('总结引用的原句不在对应发言中')
    if not any((summary.agreements, summary.factual_disagreements, summary.value_disagreements, summary.concessions, summary.open_questions)):
        raise ValueError('总结没有任何内容')


async def summarize_room(room_id, model=None):
    with store.db() as c:
        _ensure(c)
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT data FROM discussion_rooms WHERE id=?',(room_id,)).fetchone()
        if not row:
            raise HTTPException(404,'讨论室不存在')
        room=json.loads(row['data'])
        if room['status']=='generating' and _age_seconds(room)<=STALE_SECONDS:
            raise HTTPException(409,'回应仍在生成，请等它结束后再总结')
        if answered_rounds(room)<1:
            raise HTTPException(409,'分身还没有回应，暂时没有可总结的内容')
    model=model or DebateModel()
    turns=[dict(index=i,name=t['name'],text=t['text']) for i,t in enumerate(room['turns'])]
    payload={'task':'summary','topic':room['topic'],'turns':turns,
             'instruction':'仅返回严格JSON：{"agreements":[{"text":"","quotes":[{"turn":0,"quote":""}]}],"factual_disagreements":[],"value_disagreements":[],"concessions":[],"open_questions":[""]}。每组最多五条；quotes的turn是turns里的index，quote必须逐字摘自该条发言的text，不加省略号。'}
    system=SYSTEM+'''\n你要为这场讨论写总结：共识点、事实分歧、价值分歧、双方让步、仍待查证的问题。
区分事实分歧（可以查证）与价值取舍（取决于看重什么）。不能判谁赢，不推荐立场，不添加对话以外的事实或数据。
只总结对话中真实出现过的内容，不替任何一方补充他没说过的前提。'''
    correction=None
    for attempt in range(2):
        try:
            data=await model.generate(system,{**payload,**({'格式纠正':correction} if correction else {})})
            summary=RoomSummary.model_validate(data)
            validate_summary(summary,room['turns'])
            break
        except ValueError as error:
            if attempt==1:
                raise DebateError('总结没有通过原句校验：'+str(error)) from error
            correction=str(error)
    out=dict(summary.model_dump(),generated_at=store.utcnow(),note=SUMMARY_NOTE,turn_count=len(room['turns']))
    fresh=read_room(room_id)
    fresh['summary']=out
    save_room(fresh)
    return out


router=APIRouter(prefix='/api/v1/rooms',tags=['discussion rooms'])


@router.get('/playground/ui',response_class=HTMLResponse)
def playground():
    from .room_playground import PAGE
    return PAGE


@router.post('/demo',status_code=201,dependencies=[Depends(guard.limit_create)])
def demo(body:DemoRequest):
    from .personas import persist
    path=Path(__file__).resolve().parents[2]/'docs/examples/author-persona.json'
    profile=json.loads(path.read_text(encoding='utf-8'))
    persist(profile)
    return create_room(RoomRequest(persona_id=profile['id'],topic='远程办公是否应成为知识工作的默认模式',council=body.council))


@router.post('',status_code=201,dependencies=[Depends(guard.limit_create)])
def create(body:RoomRequest):
    return create_room(body)


@router.get('/{room_id}')
def read(room_id:str):
    return read_room(room_id)


@router.get('/{room_id}/report',response_class=HTMLResponse)
def report(room_id:str):
    from .room_playground import render_transcript
    room=read_room(room_id)
    return render_transcript(room,load(room['persona_id']))


@router.post('/{room_id}/messages',dependencies=[Depends(guard.limit_model)])
async def message(room_id:str,body:RoomMessage):
    result=await discuss(room_id,body.message)
    if result['status']=='failed':
        raise HTTPException(502,{'room_id':room_id,'message':result['error'],'partial_results_saved':True})
    return result


@router.post('/{room_id}/summary',response_model=RoomSummaryOut,dependencies=[Depends(guard.limit_model)])
async def summary(room_id:str):
    try:
        return await summarize_room(room_id)
    except (DebateError,ValueError) as error:
        raise HTTPException(502,str(error)) from error
