"""Official read-only tools. Credentials are read from local configuration only."""
import argparse
import asyncio
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv
from services.api.zhihu_official import OfficialClient, OfficialError


async def run(args):
    client = OfficialClient()
    if args.command == "quota":
        result = await client.quota()
    else:
        result = await client.search(args.query, args.scope, args.count, args.sort_by)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    load_dotenv(ROOT / ".env")
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    quota = commands.add_parser("quota")
    quota.add_argument("--output", type=Path)
    search = commands.add_parser("search")
    search.add_argument("query")
    search.add_argument("--scope", choices=["zhihu", "web"], default="zhihu")
    search.add_argument("--count", type=int, default=5)
    search.add_argument("--sort-by")
    search.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        asyncio.run(run(args))
    except (OfficialError, ValueError) as error:
        print(json.dumps(dict(ok=False, code=getattr(error, "code", "invalid_parameters"), message=str(error)), ensure_ascii=True))
        sys.exit(2)
