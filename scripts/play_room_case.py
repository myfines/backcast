"""Act as a user in a real-model room. Each invocation adds one human-written turn."""
import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from services.api.personas import persist
from services.api.rooms import RoomRequest,create_room,discuss


async def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--message',required=True)
    parser.add_argument('--room-id')
    parser.add_argument('--council',action='store_true')
    args=parser.parse_args()
    output=ROOT/'.local/room-case'
    output.mkdir(parents=True,exist_ok=True)
    os.environ['BACKCAST_DB']=str(output/'case.sqlite3')
    if args.room_id:
        room_id=args.room_id
    else:
        profile=json.loads((ROOT/'docs/examples/author-persona.json').read_text(encoding='utf-8'))
        persist(profile)
        room=create_room(RoomRequest(persona_id=profile['id'],topic='远程办公是否应成为知识工作的默认模式',council=args.council))
        room_id=room['id']
    room=await discuss(room_id,args.message)
    room['test_user']='Codex扮演人类用户，逐轮阅读真实模型回应后追问'
    (output/'result.json').write_text(json.dumps(room,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'id':room_id,'status':room['status'],'error':room.get('error'),'latest':room['turns'][-4:]},ensure_ascii=True))
    if room['status']=='failed':
        sys.exit(1)


if __name__=='__main__':
    asyncio.run(main())
