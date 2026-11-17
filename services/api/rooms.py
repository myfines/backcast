"""Small persistent discussion rooms: one author avatar plus an optional AI panel."""
import json
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from . import store
from .debate import DebateModel, DebateError, SYSTEM
from .personas import load, reply


class RoomRequest(BaseModel):
    persona_id: str = Field(min_length=1, max_length=64)
    topic: str = Field(min_length=4, max_length=160)
    council: bool = False


class RoomMessage(BaseModel):
    message: str = Field(min_length=4, max_length=1500)


class DemoRequest(BaseModel):
    council: bool = True


def save_room(room):
    with store.db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS discussion_rooms (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        c.execute('INSERT OR REPLACE INTO discussion_rooms VALUES (?,?)', (room['id'], json.dumps(room,ensure_ascii=False)))


def read_room(room_id):
    with store.db() as c:
        c.execute('CREATE TABLE IF NOT EXISTS discussion_rooms (id TEXT PRIMARY KEY, data TEXT NOT NULL)')
        row=c.execute('SELECT data FROM discussion_rooms WHERE id=?',(room_id,)).fetchone()
    if not row:
        raise HTTPException(404,'讨论室不存在')
    return json.loads(row['data'])


def create_room(body):
    persona=load(body.persona_id)
    room=dict(id=uuid4().hex,**body.model_dump(),author_label=persona['label'],status='ready',
              turns=[],created_at=store.utcnow(),user_role_note='用户发言可能由真人或开发者扮演，演示记录会明确标注')
    save_room(room)
    return room


def claim_room(room_id):
    # Serialize concurrent posts in SQLite, including posts from separate workers.
    with store.db() as c:
        c.execute('BEGIN IMMEDIATE')
        row=c.execute('SELECT data FROM discussion_rooms WHERE id=?',(room_id,)).fetchone()
        if not row:
            raise HTTPException(404,'讨论室不存在')
        room=json.loads(row['data'])
        if room['status']=='generating':
            raise HTTPException(409,'上一条回应仍在生成，请先等待')
        if sum(t['role']=='user' for t in room['turns']) >= 12:
            raise HTTPException(409,'本场已达十二次提问上限，请新建讨论室')
        room.update(status='generating')
        room.pop('error',None)
        c.execute('UPDATE discussion_rooms SET data=? WHERE id=?',(json.dumps(room,ensure_ascii=False),room_id))
    return room


async def discuss(room_id, message, model=None):
    room=claim_room(room_id)
    model=model or DebateModel()
    history=[{'role':t['role'],'name':t['name'],'text':t['text']} for t in room['turns']][-12:]
    room['turns'].append(dict(role='user',kind='user',name='用户',text=message,created_at=store.utcnow()))
    save_room(room)
    try:
        answer=await reply(room['persona_id'],message,model,history=history)
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
        room.update(status='ready',updated_at=store.utcnow())
    except Exception as error:
        room.update(status='failed',error=str(error) if isinstance(error,(DebateError,ValueError)) else '回应生成失败，已保留已有对话')
    save_room(room)
    return room


router=APIRouter(prefix='/api/v1/rooms',tags=['discussion rooms'])


@router.get('/playground/ui',response_class=HTMLResponse)
def playground():
    from .room_playground import PAGE
    return PAGE


@router.post('/demo',status_code=201)
def demo(body:DemoRequest):
    from .personas import persist
    path=Path(__file__).resolve().parents[2]/'docs/examples/author-persona.json'
    profile=json.loads(path.read_text(encoding='utf-8'))
    persist(profile)
    return create_room(RoomRequest(persona_id=profile['id'],topic='远程办公是否应成为知识工作的默认模式',council=body.council))


@router.post('',status_code=201)
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


@router.post('/{room_id}/messages')
async def message(room_id:str,body:RoomMessage):
    result=await discuss(room_id,body.message)
    if result['status']=='failed':
        raise HTTPException(502,{'room_id':room_id,'message':result['error'],'partial_results_saved':True})
    return result
