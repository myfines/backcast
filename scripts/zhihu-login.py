"""Run locally in the optional adapter venv. Never put cookies in arguments/chat."""

from getpass import getpass
from http.cookies import SimpleCookie
import json
import os
from pathlib import Path
import sys


def main():
    root = Path(__file__).resolve().parents[1]
    path = Path(os.getenv("ZHIHU_COOKIE_FILE") or str(root / ".local/zhihu/cookies.json"))
    print("请先在自己的浏览器正常登录知乎。")
    print("在开发者工具 Network 中复制一条知乎请求的 Cookie 请求头值。")
    print("只粘贴到下面的本机隐藏输入；不要发送到聊天或作为命令行参数。")
    raw = getpass("Cookie（输入不回显）: ").strip()
    if raw.lower().startswith("cookie:"):
        raw = raw.split(":", 1)[1].strip()
    parsed = SimpleCookie()
    parsed.load(raw)
    cookies = {k: v.value for k, v in parsed.items()}
    if not cookies.get("z_c0"):
        print("未识别到正常登录会话，未保存。")
        return 1
    try:
        from zhihu_cli.client import ZhihuClient

        with ZhihuClient(cookies) as client:
            client._session.trust_env = False
            profile = client.get_self_info()
        if not profile.get("id"):
            raise ValueError("missing identity")
    except Exception:
        print("知乎仍未接受该会话；可能是登录或访问限制。已停止，未保存凭证。")
        return 1
    path.parent.mkdir(parents=True, exist_ok=True)
    if os.name != "nt":
        path.parent.chmod(0o700)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"cookies": cookies}), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(path)
    print("登录验证通过，已保存本机会话。凭证不会进入报告或 Git。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
