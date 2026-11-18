"""Official developer.zhihu.com integration: Bearer API, never browser cookies."""

from datetime import datetime, timezone
import os
from pathlib import Path
import time
from urllib.parse import urlparse

from dotenv import dotenv_values
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from . import guard
from typing import Literal

from .zhihu import api_date, plain_text

ROOT = Path(__file__).resolve().parents[2]
BASE = "https://developer.zhihu.com"


class OfficialError(Exception):
    def __init__(self, code, message):
        self.code = code
        super().__init__(message)


def access_secret():
    value = os.getenv("ZHIHU_ACCESS_SECRET")
    if value:
        return value.strip()
    path = Path(os.getenv("ZHIHU_CREDENTIAL_FILE") or ROOT / ".local/zhihu-official.env")
    return (dotenv_values(path).get("ZHIHU_ACCESS_SECRET") or "").strip() if path.is_file() else ""


def normalize_results(data, scope, query):
    if not isinstance(data, dict) or not isinstance(data.get("Items"), list):
        raise OfficialError("invalid_response", "官方搜索返回格式无效。")
    items, seen = [], set()
    for item in data["Items"]:
        if not isinstance(item, dict):
            continue
        url = item.get("Url") or ""
        parsed = urlparse(url)
        if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password:
            continue
        if scope == "zhihu" and not (parsed.hostname == "zhihu.com" or parsed.hostname.endswith(".zhihu.com")):
            continue
        if url in seen:
            continue
        seen.add(url)
        items.append(dict(title=plain_text(item.get("Title") or "公开内容"), url=url,
                          author_name=item.get("AuthorName") or "", text=plain_text(item.get("ContentText") or ""),
                          is_excerpt=True, content_type=item.get("ContentType"),
                          published_at=api_date(item.get("CreateTime")), edited_at=None,
                          source_time=api_date(item.get("EditTime")), source_time_field="EditTime",
                          source_time_meaning="官方字段可能是发布或更新时间，未当作首次发表时间。",
                          author_identity_verified=False, original_version_verified=False,
                          provenance="zhihu-official-search"))
    return dict(provider="zhihu_official", scope=scope, query=query, items=items,
                search_id=data.get("SearchHashId"), retrieved_at=datetime.now(timezone.utc).isoformat(),
                coverage=dict(returned=len(items), complete_author_history=False,
                              has_more=data.get("HasMore"), scope="相关搜索结果；摘要不是完整原文，也不是作者全历史。"))


class OfficialClient:
    def __init__(self, secret=None, transport=None):
        self.secret = secret if secret is not None else access_secret()
        self.transport = transport

    async def _get(self, path, params=None):
        if not self.secret:
            raise OfficialError("not_configured", "尚未配置知乎官方 Access Secret。")
        if path not in ("/api/v1/quota", "/api/v1/content/zhihu_search", "/api/v1/content/global_search"):
            raise ValueError("仅允许官方额度和公开搜索接口。")
        headers = {"Authorization": "Bearer " + self.secret, "X-Request-Timestamp": str(int(time.time())),
                   "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=30, trust_env=False, follow_redirects=False, transport=self.transport) as client:
                response = await client.get(BASE + path, params=params, headers=headers)
            if response.status_code in (401, 403):
                raise OfficialError("authentication_failed", "官方凭证无效或接口未授权。")
            if response.status_code == 429:
                raise OfficialError("rate_limited", "官方接口已限流；没有自动重试。")
            if response.status_code != 200:
                raise OfficialError("upstream_error", "官方接口未成功返回；没有转发上游错误正文。")
            body = response.json()
        except (httpx.HTTPError, ValueError) as error:
            raise OfficialError("network_error", "官方接口网络或响应格式异常；未自动重试。") from error
        if not isinstance(body, dict):
            raise OfficialError("invalid_response", "官方接口返回格式无效。")
        code = body.get("Code")
        if code != 0:
            label = {20001: "authentication_failed", 30001: "rate_limited", 10001: "invalid_parameters"}.get(code, "upstream_error")
            raise OfficialError(label, "官方接口未接受本次请求；请检查权限、额度或参数。")
        if not isinstance(body.get("Data"), dict):
            raise OfficialError("invalid_response", "官方接口未返回有效数据。")
        return body["Data"]

    async def quota(self):
        return await self._get("/api/v1/quota", {"APIIDs": "zhihu_search,global_search,user_data"})

    async def search(self, query, scope="zhihu", count=5, sort_by=None):
        if scope not in ("zhihu", "web") or not isinstance(query, str) or not 2 <= len(query.strip()) <= 500:
            raise ValueError("搜索范围或查询无效。")
        if isinstance(count, bool) or not isinstance(count, int) or not 1 <= count <= (10 if scope == "zhihu" else 20):
            raise ValueError("知乎搜索最多10条，全网搜索最多20条。")
        params = {"Query": query.strip(), "Count": count}
        if sort_by:
            if scope != "zhihu" or len(sort_by) > 120:
                raise ValueError("排序参数无效。")
            params["SortBy"] = sort_by
        endpoint = "zhihu_search" if scope == "zhihu" else "global_search"
        data = await self._get("/api/v1/content/" + endpoint, params)
        return normalize_results(data, scope, query.strip())


class OfficialSearchRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    query: str = Field(min_length=2, max_length=500)
    scope: Literal["zhihu", "web"] = "zhihu"
    count: int = Field(default=5, ge=1, le=20)
    sort_by: str | None = Field(default=None, max_length=120)


router = APIRouter(prefix="/api/v1/official", tags=["official Zhihu"])


@router.get("/status")
def official_status():
    return dict(configured=bool(access_secret()), provider="zhihu_official", cookie_required=False,
                mcp_url=BASE + "/api/mcp/v1")


@router.post("/search", dependencies=[Depends(guard.limit_model)])
async def official_search(body: OfficialSearchRequest):
    try:
        return await OfficialClient().search(body.query, body.scope, body.count, body.sort_by)
    except ValueError as error:
        raise HTTPException(422, str(error)) from error
    except OfficialError as error:
        raise HTTPException(503 if error.code in ("not_configured", "authentication_failed") else 502,
                            {"code": error.code, "message": str(error)}) from error
