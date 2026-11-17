"""Run real search + hosted model, preserving failures and partial results locally."""
import asyncio
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.api.debate import DebateRequest, run_case, render_report, get
from services.api.store import utcnow


async def main():
    output = ROOT / '.local/debate-case'
    output.mkdir(parents=True, exist_ok=True)
    os.environ['BACKCAST_DB'] = str(output / 'case.sqlite3')
    data = dict(id=uuid4().hex, **DebateRequest().model_dump(), created_at=utcnow())
    if len(sys.argv) == 3 and sys.argv[1] == '--resume':
        data = get(sys.argv[2])
    result = await run_case(data)
    (output / 'result.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
    (output / 'report.html').write_text(render_report(result), encoding='utf-8')
    print(json.dumps({'id': result['id'], 'status': result['status'], 'turns': len(result.get('turns', [])), 'sources': len(result.get('sources', [])), 'error': result.get('error')}, ensure_ascii=True))
    if result['status'] != 'completed':
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())
