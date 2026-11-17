"""Isolated, read-only pyzhihu-cli bridge. Credentials never leave this process."""

import json
import os
from pathlib import Path
import sys
from datetime import datetime, timezone


def main():
    request = json.loads(sys.stdin.read())
    try:
        from zhihu_cli.client import ZhihuClient
        from zhihu_cli.exceptions import LoginError
    except ImportError:
        return {
            "ok": False,
            "code": "setup_required",
            "message": "请安装 requirements-zhihu.txt 或配置 ZHIHU_PYTHON。",
        }
    cookie_file = Path(
        os.getenv("ZHIHU_COOKIE_FILE")
        or str(Path(__file__).resolve().parents[2] / ".local/zhihu/cookies.json")
    )
    cookies = {}
    if cookie_file.is_file():
        try:
            data = json.loads(cookie_file.read_text(encoding="utf-8"))
            cookies = data.get("cookies", data)
            if not isinstance(cookies, dict) or not all(
                isinstance(k, str) and isinstance(v, str) for k, v in cookies.items()
            ):
                raise ValueError()
        except (ValueError, OSError):
            return {
                "ok": False,
                "code": "invalid_session",
                "message": "本机登录文件格式无效，请重新登录。",
            }
    guard_path = Path(__file__).resolve().parents[2] / ".local/zhihu/access-state.json"
    session_stamp = (
        str(cookie_file.resolve())
        + ":"
        + str(cookie_file.stat().st_mtime_ns if cookie_file.is_file() else None)
    )
    operation = request["operation"]
    target = request["target"]
    if guard_path.is_file():
        try:
            guard = json.loads(guard_path.read_text(encoding="utf-8"))
            if (
                guard.get("session_stamp") == session_stamp
                and guard.get("operation") == operation
                and guard.get("target") == target
            ):
                return {
                    "ok": False,
                    "code": guard["code"],
                    "message": "同一会话访问该资源已被拒绝；请正常登录后再试，没有重复网络请求。",
                }
        except (OSError, ValueError, KeyError):
            pass
    with ZhihuClient(cookies) as client:
        client._session.trust_env = False
        client._session.max_redirects = 3
        operation = request["operation"]
        target = request["target"]
        try:
            if operation == "profile":
                data = client.get_user_profile(target)
            elif operation == "answer":
                data = client.get_answer(target)
            elif operation in ("answers", "articles"):
                method = (
                    client.get_user_answers if operation == "answers" else client.get_user_articles
                )
                data = method(
                    target, offset=request.get("offset", 0), limit=request.get("limit", 10)
                )
            else:
                return {
                    "ok": False,
                    "code": "invalid_operation",
                    "message": "只允许查询公开资料、回答及文章。",
                }
            return {"ok": True, "data": data}
        except LoginError:
            guard_path.parent.mkdir(parents=True, exist_ok=True)
            guard_path.write_text(
                json.dumps(
                    {
                        "session_stamp": session_stamp,
                        "operation": operation,
                        "target": target,
                        "code": "blocked" if cookies else "needs_login",
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                        "source": "actual_read_denied",
                    }
                ),
                encoding="utf-8",
            )
            return {
                "ok": False,
                "code": "blocked" if cookies else "needs_login",
                "message": "知乎拒绝访问，请正常登录或检查平台访问限制；已停止请求。",
            }
        except Exception as error:
            code = "rate_limited" if "429" in str(error) else "network_error"
            return {
                "ok": False,
                "code": code,
                "message": "知乎请求失败，未继续重试；请检查网络或访问状态。",
            }


if __name__ == "__main__":
    try:
        result = main()
    except Exception:
        result = {
            "ok": False,
            "code": "invalid_response",
            "message": "知乎桥接程序未能取得有效结果。",
        }
    print(json.dumps(result, ensure_ascii=True))
