"""Bounded historical collection using the Apache-2.0 pyzhihu-cli library."""

from datetime import datetime, timezone
from hashlib import sha256
from html.parser import HTMLParser
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import urlparse


class AccessBlocked(Exception):
    def __init__(self, code, message, partial=None):
        super().__init__(message)
        self.code = code
        self.partial = partial


def normalize_target(value):
    value = value.strip()
    if "://" in value:
        u = urlparse(value)
        if (
            u.scheme != "https"
            or u.hostname not in ("www.zhihu.com", "zhihu.com")
            or u.username
            or u.password
        ):
            raise ValueError("请提供知乎 HTTPS 个人主页链接。")
        match = re.fullmatch(
            r"/people/([A-Za-z0-9_-]+)(?:/(?:answers|posts|activities))?/?", u.path
        )
        if not match:
            raise ValueError("需要知乎个人主页，不能用问题或其他站点链接。")
        value = match[1]
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", value):
        raise ValueError("答主标识无效；请粘贴个人主页链接。")
    return value


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self.hidden += 1
        elif not self.hidden and tag in ("p", "br", "li", "div", "h1", "h2", "h3"):
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.hidden = max(0, self.hidden - 1)
        elif not self.hidden and tag in ("p", "li", "div"):
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def plain_text(html):
    parser = PlainText()
    parser.feed(str(html or ""))
    return "\n".join(s.strip() for s in "".join(parser.parts).splitlines() if s.strip())


def api_date(value):
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        try:
            return datetime.fromtimestamp(value, timezone.utc).isoformat()
        except (OverflowError, OSError, ValueError):
            return None
    return None


def normalize_document(item, kind, target):
    author = item.get("author") or {}
    if author.get("url_token") and author["url_token"] != target:
        raise ValueError("返回内容的作者与目标不一致。")
    id = str(item.get("id") or "")
    if not id.isdigit():
        raise ValueError("平台返回的内容 ID 无效。")
    question = item.get("question") or {}
    question_id = str(question.get("id") or "")
    url = (
        (
            f"https://www.zhihu.com/question/{question_id}/answer/{id}"
            if question_id.isdigit()
            else f"https://www.zhihu.com/answer/{id}"
        )
        if kind == "answer"
        else f"https://zhuanlan.zhihu.com/p/{id}"
    )
    text = plain_text(item.get("content") or "")
    return {
        "id": "zhihu-" + kind + "-" + id,
        "platform_id": id,
        "kind": kind,
        "url": url,
        "title": item.get("title") or question.get("title") or "知乎公开内容",
        "text": text[:40000],
        "text_truncated": len(text) > 40000,
        "published_at": api_date(item.get("created_time") or item.get("created")),
        "edited_at": api_date(item.get("updated_time") or item.get("updated")),
        "author_token": target,
        "content_sha256": sha256(text.encode()).hexdigest(),
        "capture_method": "pyzhihu-cli-web-api",
        "identity_confirmed_by_item": author.get("url_token") == target,
    }


class LibraryTransport:
    def __init__(self):
        root = Path(__file__).resolve().parents[2]
        local = (
            root / ".venv/zhihu-probe" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        )
        self.python = os.getenv("ZHIHU_PYTHON") or (
            str(local) if local.is_file() else sys.executable
        )

    def call(self, operation, target, offset=0, limit=10):
        try:
            result = subprocess.run(
                [self.python, str(Path(__file__).with_name("zhihu_worker.py"))],
                input=json.dumps(
                    {"operation": operation, "target": target, "offset": offset, "limit": limit}
                ),
                text=True,
                encoding="utf-8",
                capture_output=True,
                timeout=35,
            )
            payload = json.loads(result.stdout)
        except (OSError, ValueError, subprocess.TimeoutExpired) as error:
            raise AccessBlocked("network_error", "知乎读取程序未返回有效结果；已停止。") from error
        if not payload.get("ok"):
            raise AccessBlocked(
                payload.get("code", "failed"), payload.get("message", "知乎读取失败。")
            )
        if not isinstance(payload.get("data"), dict):
            raise ValueError("知乎返回了无效数据。")
        return payload["data"]


def collect_history(transport, target, max_items=20, max_pages=3, kinds=None):
    target = normalize_target(target)
    kinds = kinds or ["answer", "article"]
    profile = transport.call("profile", target)
    if profile.get("url_token") and profile["url_token"] != target:
        raise ValueError("返回的答主身份与目标不一致。")
    documents = []
    seen = set()
    reached = {}
    warnings = []
    requests = 1
    for kind in kinds:
        offset = 0
        reached[kind] = False
        for _ in range(max_pages):
            remaining = max_items - len(documents)
            if remaining <= 0:
                warnings.append("采集达到条数预算，不代表全量历史。")
                break
            try:
                data = transport.call(
                    "answers" if kind == "answer" else "articles",
                    target,
                    offset,
                    min(10, remaining),
                )
                requests += 1
            except AccessBlocked as error:
                error.partial = {
                    "profile": {
                        "name": profile.get("name") or target,
                        "url_token": target,
                        "headline": profile.get("headline", ""),
                    },
                    "documents": documents,
                    "coverage": {
                        "captured": len(documents),
                        "complete": False,
                        "reached_end": reached,
                        "requests": requests + 1,
                        "warnings": ["采集中途被拒绝，已保留先前取得的正文；未重试。"],
                    },
                }
                raise
            items = data.get("data", [])
            if not isinstance(items, list):
                raise ValueError("知乎列表格式无效。")
            new = 0
            for item in items[:remaining]:
                document = normalize_document(item, kind, target)
                if document["id"] in seen:
                    continue
                seen.add(document["id"])
                new += 1
                # The list endpoint may omit full content; obtain answer details when needed.
                if not document["text"] and kind == "answer":
                    detail = transport.call("answer", document["platform_id"])
                    requests += 1
                    document = normalize_document(detail, kind, target)
                if document["text"]:
                    documents.append(document)
                else:
                    warnings.append("部分条目没有正文，未计入可分析材料。")
            paging = data.get("paging") or {}
            if paging.get("is_end") is True:
                reached[kind] = True
                break
            if not items:
                warnings.append("空页未提供结束标识，不能确认全量。")
                break
            if new == 0:
                warnings.append("分页重复，已停止避免循环。")
                break
            offset += len(items)
        else:
            warnings.append("达到分页预算，不代表全量历史。")
    dates = sorted(d["published_at"] for d in documents if d["published_at"])
    return {
        "profile": {
            "name": profile.get("name") or target,
            "url_token": target,
            "headline": profile.get("headline") or "",
            "answer_count": profile.get("answer_count"),
            "article_count": profile.get("articles_count"),
        },
        "documents": documents,
        "coverage": {
            "captured": len(documents),
            "reached_end": reached,
            "complete": all(reached.values()) and not warnings,
            "requests": requests,
            "first_published_at": dates[0] if dates else None,
            "last_published_at": dates[-1] if dates else None,
            "warnings": list(dict.fromkeys(warnings)),
        },
    }
