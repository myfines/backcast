"""Local bridge: export actual task input to an analyst and submit its JSON answer."""

import argparse
import json
from pathlib import Path
import sys
import httpx
from dotenv import dotenv_values

root = Path(__file__).resolve().parents[1]


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base-url", default="http://127.0.0.1:8000")
    sub = p.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("target")
    create.add_argument("--goal", required=True)
    create.add_argument("--domain", default="其他")
    for name in ("status", "retry"):
        sub.add_parser(name).add_argument("id")
    inp = sub.add_parser("input")
    inp.add_argument("id")
    inp.add_argument("--output", required=True)
    submit = sub.add_parser("submit")
    submit.add_argument("id")
    submit.add_argument("file")
    args = p.parse_args()
    headers = {}
    if args.command in ("input", "submit"):
        token = dotenv_values(root / ".env").get("RESEARCH_WORKER_TOKEN")
        if not token:
            raise SystemExit("后端 .env 尚未配置 RESEARCH_WORKER_TOKEN。")
        headers = {"X-Worker-Token": token}
    with httpx.Client(base_url=args.base_url, timeout=180, trust_env=False) as client:
        path = "/api/v1/research-jobs"
        if args.command == "create":
            r = client.post(
                path,
                json={
                    "target": args.target,
                    "goal": args.goal,
                    "domain": args.domain,
                    "analyst": "worker",
                },
            )
        elif args.command == "retry":
            r = client.post(path + "/" + args.id + "/retry")
        elif args.command == "status":
            r = client.get(path + "/" + args.id)
        elif args.command == "input":
            r = client.get(path + "/" + args.id + "/input", headers=headers)
        else:
            r = client.post(
                path + "/" + args.id + "/analysis",
                json=json.loads(Path(args.file).read_text(encoding="utf-8")),
                headers=headers,
            )
        if not r.is_success:
            print(
                json.dumps(
                    {"status": r.status_code, "detail": r.json().get("detail")}, ensure_ascii=False
                )
            )
            sys.exit(1)
        data = r.json()
    if args.command == "input":
        path = Path(args.output)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        print("已导出任务原文与提示词；没有导出工作器令牌。")
    else:
        print(json.dumps(data, ensure_ascii=False, indent=2))
