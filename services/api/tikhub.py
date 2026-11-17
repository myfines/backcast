"""Bounded, read-only TikHub probe; separate credentials from official Zhihu."""

import os
from urllib.parse import urlparse, parse_qs
import httpx

from .zhihu import normalize_target, plain_text, api_date


class TikHubError(Exception):
    def __init__(self, code, message, partial=None):
        self.code, self.partial = code, partial
        super().__init__(message)


class TikHubReader:
    def __init__(self, key=None, transport=None):
        self.key = key if key is not None else os.getenv("TIKHUB_API_KEY", "")
        self.transport, self.requests = transport, 0

    def call(self, operation, target, offset="0", limit=3):
        if not self.key:
            raise TikHubError("not_configured", "请在本机.env配置独立的TIKHUB_API_KEY；没有使用知乎官方凭证。")
        endpoint = {"profile":"fetch_user_info", "answers":"fetch_user_answers", "articles":"fetch_user_articles"}.get(operation)
        if not endpoint:
            raise ValueError("只允许读取作者资料、回答和文章列表。")
        if self.requests >= 3:
            raise TikHubError("request_budget", "达到本次3次请求上限，已停止。")
        params = {"user_url_token":normalize_target(target)}
        if operation != "profile":
            params.update(offset=str(offset), limit=str(limit), sort_type="created")
        self.requests += 1
        try:
            with httpx.Client(timeout=35, follow_redirects=False, trust_env=False, transport=self.transport) as client:
                response = client.get("https://api.tikhub.io/api/v1/zhihu/web/"+endpoint,
                                      params=params, headers={"Authorization":"Bearer "+self.key})
            if response.status_code in (401,403):
                raise TikHubError("access_denied", "TikHub拒绝请求；请检查该服务的密钥与接口权限，未自动重试。")
            if response.status_code == 402:
                raise TikHubError("balance_required", "TikHub提示余额或套餐不足；没有充值或重试。")
            if response.status_code == 429:
                raise TikHubError("rate_limited", "TikHub限流，已停止。")
            if response.status_code != 200:
                raise TikHubError("upstream_error", "TikHub未成功返回，未输出上游错误正文。")
            payload = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise TikHubError("network_error", "TikHub网络或响应格式异常；没有自动重试。") from error
        if not isinstance(payload,dict) or payload.get("code") != 200 or not isinstance(payload.get("data"),dict):
            raise TikHubError("invalid_response", "TikHub未返回预期的成功数据；没有认定采集成功。")
        return payload["data"]


def probe_author(reader, target, pages=2, limit=3, kind="answer"):
    target = normalize_target(target)
    if not 1 <= pages <= 2 or not 1 <= limit <= 10 or kind not in ("answer","article"):
        raise ValueError("探测最多2页，每页1至10条，只接受回答或文章。")
    result = dict(target=target, provider="tikhub", kind=kind, items=[], reached_end=False,
                  complete_history=False, request_limit=3, profile={}, warnings=[])
    try:
        profile = reader.call("profile", target)
        if profile.get("url_token") and profile["url_token"] != target:
            raise TikHubError("identity_mismatch", "返回作者与目标不一致。")
        result["profile"] = {key:profile.get(key) for key in ("name","url_token","answer_count","articles_count")}
        offset, offsets, seen = "0", {"0"}, set()
        for _ in range(pages):
            page = reader.call("answers" if kind=="answer" else "articles",target,offset,limit)
            if not isinstance(page.get("data"),list):
                raise TikHubError("schema_changed", "列表响应结构与预期不一致，需要按真实响应调整；未猜测正文。")
            new = 0
            for item in page["data"]:
                if not isinstance(item,dict) or str(item.get("id","")) in seen:
                    continue
                id = str(item.get("id", ""))
                if not id.isdigit():
                    raise TikHubError("invalid_item", "返回的内容标识无效。")
                author = item.get("author") or {}
                if author.get("url_token") and author["url_token"] != target:
                    raise TikHubError("identity_mismatch", "内容作者与目标不一致，已停止。")
                text = plain_text(item.get("content") or "")
                seen.add(id);new += 1
                result["items"].append(dict(id=id, title=item.get("title") or (item.get("question") or {}).get("title"),
                    author_token=author.get("url_token"), author_confirmed=author.get("url_token")==target,
                    body_characters=len(text), text=text, has_body_content=bool(text), completeness_verified=False,
                    published_at=api_date(item.get("created_time") or item.get("created")),
                    edited_at=api_date(item.get("updated_time") or item.get("updated")),
                    raw=item))
            paging = page.get("paging") or {}
            if paging.get("is_end") is True:
                result["reached_end"] = True
                break
            if not new:
                result["warnings"].append("空页或重复页，没有确认历史末尾。")
                break
            # Parse only the next offset; never follow a provider-supplied URL with our token.
            next_offset = parse_qs(urlparse(str(paging.get("next") or "")).query).get("offset",[None])[0]
            if next_offset is None or next_offset in offsets or len(next_offset)>200:
                result["warnings"].append("下一页游标缺失或重复，停止，未擅自推算。")
                break
            offsets.add(next_offset);offset=next_offset
        result["requests"] = reader.requests if hasattr(reader,"requests") else None
        return result
    except TikHubError as error:
        result["requests"] = reader.requests if hasattr(reader,"requests") else None
        error.partial = result
        raise
