"""Read-only adapter for amchii/ZhiArchive's published MCP interface (MIT).

Independent integration, not a copy of its crawler. ZhiArchive owns its normal
login and browser lifecycle; Backcast receives only public content, not cookies.
"""

from contextlib import AsyncExitStack
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
import re
from urllib.parse import urlparse

from .zhihu import AccessBlocked, normalize_target, plain_text


class ZhiArchiveGateway:
    allowed = {"get_zhihu_auth_status", "list_zhihu_profile_items", "read_zhihu_content"}

    def __init__(self, url=None, token=None):
        self.url = url or os.getenv("ZHIARCHIVE_MCP_URL", "http://127.0.0.1:9090/mcp/")
        self.token = token if token is not None else os.getenv("ZHIARCHIVE_TOKEN", "")
        parsed = urlparse(self.url)
        if (parsed.scheme not in ("http", "https") or not parsed.hostname
                or parsed.username or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("ZhiArchive 地址无效；凭证只能通过后端环境变量传入。")
        if parsed.scheme == "http" and parsed.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("远程 ZhiArchive 必须使用 HTTPS。")
        self.stack = AsyncExitStack()

    async def __aenter__(self):
        try:
            from mcp import ClientSession
            from mcp.client.streamable_http import streamablehttp_client
        except ImportError as error:
            raise AccessBlocked("setup_required", "请安装 requirements-zhiarchive.txt。") from error
        try:
            headers = {"Authorization": "Bearer " + self.token} if self.token else None
            read, write, _ = await self.stack.enter_async_context(
                streamablehttp_client(self.url, headers=headers, timeout=10, sse_read_timeout=90)
            )
            self.session = await self.stack.enter_async_context(ClientSession(read, write))
            await self.session.initialize()
            return self
        except BaseException:
            await self.stack.aclose()
            raise

    async def __aexit__(self, *args):
        return await self.stack.__aexit__(*args)

    async def call(self, name, arguments):
        if name not in self.allowed:
            raise ValueError("只允许读取登录摘要、作者列表和公开正文。")
        result = await self.session.call_tool(name, arguments)
        if result.isError:
            message = " ".join(getattr(block, "text", "") for block in result.content)
            code = "collector_error"
            for markers, value in [(("403", "拒绝"), "blocked"), (("429", "冷却"), "rate_limited"),
                                   (("登录", "login", "401"), "needs_login"),
                                   (("timeout", "超时"), "collector_timeout")]:
                if any(s in message.lower() for s in markers):
                    code = value
                    break
            raise AccessBlocked(code, f"ZhiArchive 读取失败（{code}）；已停止，不重复请求。")
        data = result.structuredContent
        if not isinstance(data, dict):
            blocks = [b.text for b in result.content if getattr(b, "type", None) == "text"]
            try:
                data = json.loads("\n".join(blocks))
            except ValueError as error:
                raise ValueError("ZhiArchive 返回格式无效。") from error
        if not isinstance(data, dict):
            raise ValueError("ZhiArchive 返回格式无效。")
        return data


def date(value):
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        # Do not interpret a timezone-free display value as a known instant.
        return parsed.astimezone(timezone.utc).isoformat() if parsed.tzinfo else None
    except ValueError:
        return None


def content_url(url, kind):
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.username or parsed.password or parsed.port not in (None, 443):
        raise ValueError("采集器返回了无效公开链接。")
    if kind == "answer" and parsed.hostname in ("www.zhihu.com", "zhihu.com"):
        match = re.fullmatch(r"/(?:question/\d+/)?answer/(\d+)/?", parsed.path)
    elif kind == "article" and parsed.hostname == "zhuanlan.zhihu.com":
        match = re.fullmatch(r"/p/(\d+)/?", parsed.path)
    else:
        match = None
    if not match:
        raise ValueError("采集器返回了不匹配的内容链接。")
    return match[1]


async def collect_zhiarchive(gateway, target, max_items=20, max_pages=3, kinds=None):
    target = normalize_target(target)
    kinds = kinds or ["answer", "article"]
    if not 1 <= max_items <= 40 or not 1 <= max_pages <= 5 or any(k not in ("answer", "article") for k in kinds):
        raise ValueError("采集预算或类型无效。")
    docs, seen, reached, warnings = [], set(), {}, []
    profile = {"name": target, "url_token": target, "headline": ""}
    requests = 0

    async def call(name, arguments):
        nonlocal requests
        requests += 1
        return await gateway.call(name, arguments)

    def collected():
        dates = sorted(d["published_at"] for d in docs if d["published_at"])
        return dict(profile=profile, documents=docs, coverage=dict(
            collector="zhiarchive-mcp", captured=len(docs), complete=all(reached.values()) and not warnings,
            reached_end=dict(reached), requests=requests, warnings=list(dict.fromkeys(warnings)),
            first_published_at=dates[0] if dates else None, last_published_at=dates[-1] if dates else None))

    try:
        for kind in kinds:
            reached[kind] = False
            cursor, cursors = None, set()
            for _ in range(max_pages):
                remaining = max_items - len(docs)
                if remaining <= 0:
                    warnings.append("达到条数预算，不代表全量历史。")
                    break
                page = await call("list_zhihu_profile_items", dict(
                    people=target, content_type=kind, cursor=cursor, limit=min(20, remaining)))
                if page.get("people") != target or page.get("content_type") != kind or not isinstance(page.get("items"), list):
                    raise ValueError("列表类型或作者不匹配。")
                new = 0
                for item in page["items"][:remaining]:
                    url = item.get("url", "")
                    identity = content_url(url, kind)
                    key = (kind, identity)
                    if key in seen:
                        continue
                    seen.add(key)
                    new += 1
                    parts, offset, metadata, truncated = [], 0, None, False
                    # MCP returns bounded character pages, not necessarily full text.
                    for part_index in range(4):
                        part = await call("read_zhihu_content", dict(url=url, content_format="html", offset=offset))
                        if (content_url(part.get("url", ""), kind) != identity
                                or normalize_target(part.get("author_url", "")) != target
                                or part.get("offset") != offset or not isinstance(part.get("content"), str)):
                            raise ValueError("正文身份、链接或分页位置不匹配。")
                        metadata = metadata or part
                        chunk = part["content"]
                        parts.append(chunk)
                        truncated = part.get("truncated") is True
                        if not truncated:
                            break
                        next_offset = part.get("next_offset")
                        if not isinstance(next_offset, int) or next_offset != offset + len(chunk) or not chunk:
                            raise ValueError("正文分页游标无效。")
                        offset = next_offset
                        if sum(map(len, parts)) >= 40000:
                            break
                    text = plain_text("".join(parts))
                    if not text.strip():
                        warnings.append("部分条目没有可读正文，未计入材料。")
                        continue
                    truncated = truncated or len(text) > 40000
                    if truncated:
                        warnings.append("部分正文超过读取预算，已明确标记截断。")
                    docs.append(dict(id=f"zhihu-{kind}-{identity}", platform_id=identity, kind=kind,
                                     url=url, title=metadata.get("title") or item.get("title") or "知乎公开内容",
                                     text=text[:40000], text_truncated=truncated,
                                     published_at=date(metadata.get("published_at")) or date(item.get("created_at")),
                                     edited_at=date(metadata.get("updated_at")) or date(item.get("updated_at")),
                                     author_token=target, identity_confirmed_by_item=True,
                                     capture_method="zhiarchive-mcp", content_sha256=sha256(text[:40000].encode()).hexdigest()))
                    if metadata.get("author"):
                        profile["name"] = metadata["author"]
                if page.get("has_more") is False and page.get("next_cursor") is None:
                    reached[kind] = True
                    break
                next_cursor = page.get("next_cursor")
                if (not new or not isinstance(next_cursor, str) or not next_cursor.isdigit()
                        or int(next_cursor) <= int(cursor or 0) or next_cursor in cursors):
                    warnings.append("分页缺失或重复，已停止；不能确认全量历史。")
                    break
                cursors.add(next_cursor)
                cursor = next_cursor
            else:
                warnings.append("达到分页预算，不代表全量历史。")
    except AccessBlocked as error:
        warnings.append("中途拒绝访问；已停止并保留先前正文。")
        error.partial = collected()
        raise
    return collected()


async def configured_history(target, max_items=20, max_pages=3, kinds=None):
    try:
        async with ZhiArchiveGateway() as gateway:
            return await collect_zhiarchive(gateway, target, max_items, max_pages, kinds)
    except (AccessBlocked, ValueError):
        raise
    except Exception as error:
        # MCP's task groups can wrap a tool denial during context shutdown.
        # Preserve that denial and already captured documents, not 'unavailable'.
        def find_denial(exception):
            if isinstance(exception, AccessBlocked):
                return exception
            for child in getattr(exception, "exceptions", ()):
                found = find_denial(child)
                if found:
                    return found
            return None
        denial = find_denial(error)
        if denial:
            raise denial from None
        raise AccessBlocked("collector_unavailable", "ZhiArchive 服务不可用，请先启动本地采集服务；未生成空历史结论。") from error
