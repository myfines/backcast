"""Persistent Edge login and bounded, resumable public-history export."""

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from services.api.edge_collector import PROFILE, run_edge, now
from services.api.zhihu import AccessBlocked


def login():
    from playwright.sync_api import sync_playwright
    PROFILE.mkdir(parents=True, exist_ok=True)
    print("请在专用 Edge 窗口正常登录知乎。无需复制或发送 Cookie。", flush=True)
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(str(PROFILE), channel="msedge", headless=False, chromium_sandbox=True)
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto("https://www.zhihu.com/signin", wait_until="domcontentloaded")
            page.get_by_role("img", name=re.compile("点击打开.+的主页")).first.wait_for(state="visible", timeout=300000)
            (PROFILE.parent / "edge-login.json").write_text(json.dumps(dict(
                logged_in_at=now(), method="normal_interactive_browser_login")), encoding="utf-8")
            print("登录完成，本机专用配置已保存；可以运行 collect。", flush=True)
        finally:
            context.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("login")
    commands.add_parser("status")
    collect = commands.add_parser("collect")
    collect.add_argument("target")
    collect.add_argument("--limit", type=int, default=20)
    collect.add_argument("--pages", type=int, default=3)
    collect.add_argument("--kinds", nargs="+", choices=["answer", "article"], default=["answer"])
    collect.add_argument("--fresh", action="store_true", help="Read again without loading or overwriting checkpoints")
    collect.add_argument("--output", type=Path, default=ROOT / ".local/zhihu/edge-export.json")
    args = parser.parse_args()
    try:
        if args.command == "login":
            login()
        elif args.command == "status":
            print(json.dumps(dict(profile_exists=(PROFILE / "Default").is_dir(),
                                  login_completed=(PROFILE.parent / "edge-login.json").is_file(),
                                  note="本机状态不等于服务器仍接受会话；collect 会实际检查。"), ensure_ascii=False))
        else:
            result = run_edge(args.target, args.limit, args.pages, args.kinds, not args.fresh)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            print(json.dumps(dict(ok=True, coverage=result["coverage"], output=str(args.output.resolve())), ensure_ascii=False))
    except AccessBlocked as error:
        if getattr(args, "output", None) and error.partial:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(error.partial, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(dict(ok=False, code=error.code, message=str(error),
                              captured=len((error.partial or {}).get("documents", []))), ensure_ascii=False))
        sys.exit(2)
    except Exception as error:
        print(json.dumps(dict(ok=False, code="tool_error", error_type=type(error).__name__,
                              message="操作未完成，未输出凭证；请检查 Edge 安装、窗口占用或登录状态。"), ensure_ascii=False))
        sys.exit(1)
