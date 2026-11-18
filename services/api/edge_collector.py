"""DOM-only history collection with an operator-owned persistent Edge profile.

No cookie export, private API calls, stealth scripts or browser-profile copying.
The pure collection loop is independent of Playwright and future model APIs.
"""

from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import subprocess
import sys
import time

from .zhihu import AccessBlocked, normalize_target
from .zhiarchive import content_url, date

ROOT = Path(__file__).resolve().parents[2]
PROFILE = ROOT / ".local/zhihu/edge-profile"


def now():
    return datetime.now(timezone.utc).isoformat()


def normalize_snapshot(raw, kind, target):
    target = normalize_target(target)
    identity = content_url(raw.get("url", ""), kind)
    if normalize_target(raw.get("author_url", "")) != target:
        raise ValueError("正文作者不匹配，不能归入目标历史。")
    text = raw.get("text")
    if raw.get("folded") is not False or not isinstance(text, str) or not text.strip():
        raise ValueError("正文仍折叠或为空，不能把摘要当作完整材料。")
    return dict(id=f"zhihu-{kind}-{identity}", platform_id=identity, kind=kind,
                url=raw["url"], title=raw.get("title") or "知乎公开内容", text=text[:40000],
                text_truncated=len(text) > 40000, author_token=target,
                author_name=raw.get("author_name") or target,
                published_at=date(raw.get("published_at")), edited_at=date(raw.get("edited_at")),
                capture_method="edge-visible-dom", original_version_verified=False,
                identity_confirmed_by_item=True, captured_at=now(),
                content_sha256=sha256(text[:40000].encode()).hexdigest())


class Checkpoint:
    def __init__(self, path, target, kinds):
        self.path, self.target, self.kinds = Path(path), normalize_target(target), kinds

    def load(self):
        if not self.path.exists():
            return []
        if self.path.stat().st_size > 25_000_000:
            raise ValueError("断点文件过大。")
        data = json.loads(self.path.read_text(encoding="utf-8"))
        if data.get("version") != 1 or data.get("target") != self.target or data.get("kinds") != self.kinds:
            raise ValueError("断点的作者或内容类型与本次任务不一致。")
        documents = data.get("documents")
        if not isinstance(documents, list) or len(documents) > 500:
            raise ValueError("断点格式无效。")
        for doc in documents:
            if (doc.get("author_token") != self.target or doc.get("kind") not in self.kinds
                    or not isinstance(doc.get("text"), str) or not doc["text"].strip()
                    or doc.get("content_sha256") != sha256(doc["text"].encode()).hexdigest()):
                raise ValueError("断点正文或作者校验失败。")
            content_url(doc["url"], doc["kind"])
        return documents

    def save(self, documents):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(".tmp")
        temporary.write_text(json.dumps(dict(version=1, target=self.target, kinds=self.kinds,
                                             documents=documents), ensure_ascii=False), encoding="utf-8")
        temporary.replace(self.path)


def collect_dom_history(reader, target, max_items=20, max_pages=3, kinds=None, checkpoint=None):
    target = normalize_target(target)
    kinds = kinds or ["answer", "article"]
    if (not 1 <= max_items <= 500 or not 1 <= max_pages <= 100
            or not kinds or len(set(kinds)) != len(kinds) or any(k not in ("answer", "article") for k in kinds)):
        raise ValueError("采集数量、页数或类型无效。")
    cached = checkpoint.load() if checkpoint else []
    all_docs = {d["url"]: d for d in cached}
    docs = list(cached[:max_items])
    cached_count = len(docs)
    reached, warnings = {}, []
    profile = dict(name=target, url_token=target, headline="")

    def result():
        return dict(profile=profile, documents=docs, coverage=dict(
            collector="edge-visible-dom", captured=len(docs), cached=cached_count,
            newly_captured=len(docs) - cached_count, complete=bool(reached) and all(reached.values()) and not warnings,
            reached_end=dict(reached), warnings=list(dict.fromkeys(warnings)),
            checkpoint_scope="缓存正文保留原采集时间，不代表本次重新访问或已证明原始历史版本。"))

    try:
        for kind in kinds:
            reached[kind] = False
            profile.update(reader.open_profile(target, kind))
            for _ in range(max_pages):
                for item in reader.list_items():
                    if len(docs) >= max_items:
                        break
                    url = item["url"]
                    content_url(url, kind)
                    if url in all_docs:
                        continue
                    raw = reader.read(url, kind)
                    if raw.get("url") != url:
                        raise ValueError("正文链接与列表条目不匹配。")
                    doc = normalize_snapshot(raw, kind, target)
                    docs.append(doc)
                    all_docs[url] = doc
                    if checkpoint:
                        checkpoint.save(list(all_docs.values()))
                if len(docs) >= max_items:
                    warnings.append("达到条数预算，不代表完整历史。")
                    break
                state = reader.more()
                if state == "end":
                    reached[kind] = True
                    break
                if state != "more":
                    warnings.append("等待加载后仍无新条目；不是已确认的历史末尾。")
                    break
            else:
                warnings.append("达到加载页数预算，不代表完整历史。")
    except AccessBlocked as error:
        warnings.append("访问受限或需要登录，已停止；先前正文已保留。")
        error.partial = result()
        raise
    return result()


CARD_SCRIPT = """root => {
 const author = root.querySelector('.AuthorInfo-name a[href*="/people/"]') || root.querySelector('a[href*="/people/"]');
 const body = root.querySelector('.RichContent-inner .RichText') || root.querySelector('.Post-RichTextContainer');
 const value = key => root.querySelector('meta[itemprop="'+key+'"]')?.content || null;
 const titleLink = root.querySelector('.ContentItem-title a');
 return {url:titleLink?.href || location.href, title:root.querySelector('.ContentItem-title')?.innerText || document.querySelector('h1')?.innerText,
 author_url:author?.href, author_name:author?.innerText,
 text:body?.innerText || '', folded:Array.from(root.querySelectorAll('button')).some(b=>b.innerText.includes('阅读全文')),
 published_at:value('dateCreated') || value('datePublished'), edited_at:value('dateModified')};
}"""


class EdgeDOMReader:
    def __init__(self, context):
        self.page, self.detail = context.new_page(), context.new_page()
        self.denied = False
        for page in (self.page, self.detail):
            page.on("response", self._response)

    def _response(self, response):
        if response.status in (403, 429) and "zhihu.com/" in response.url:
            self.denied = True

    def check(self, page):
        if self.denied:
            raise AccessBlocked("blocked", "知乎拒绝或限制访问，已停止；请在专用 Edge 窗口正常检查访问状态。")
        if "/signin" in page.url:
            raise AccessBlocked("needs_login", "请先运行 python scripts/zhihu-edge.py login 完成一次正常登录。")

    def open_profile(self, target, kind):
        suffix = "answers" if kind == "answer" else "posts"
        self.kind = kind
        self.page.goto(f"https://www.zhihu.com/people/{target}/{suffix}", wait_until="domcontentloaded")
        self.check(self.page)
        self.selector = ".AnswerItem" if kind == "answer" else ".ArticleItem"
        try:
            self.page.locator(self.selector).first.wait_for(state="visible", timeout=20000)
        except Exception as error:
            self.check(self.page)
            raise AccessBlocked("not_ready", "等待20秒仍未加载出列表；没有把空白页认定为空历史。") from error
        self.check(self.page)
        return dict(name=self.page.locator("h1").first.inner_text().strip(), url_token=target)

    def list_items(self):
        self.check(self.page)
        return self.page.locator(self.selector).evaluate_all("nodes => nodes.map(e=>({url:e.querySelector('.ContentItem-title a')?.href})).filter(x=>x.url)")

    def read(self, url, kind):
        time.sleep(0.8)
        self.detail.goto(url, wait_until="domcontentloaded")
        self.check(self.detail)
        root = self.detail.locator(".AnswerItem").first if kind == "answer" else self.detail.locator("body")
        body = root.locator(".RichContent-inner .RichText" if kind == "answer" else ".Post-RichTextContainer")
        try:
            body.first.wait_for(state="visible", timeout=20000)
            expand = root.get_by_role("button", name="阅读全文", exact=False)
            if expand.count():
                expand.first.click()
                expand.first.wait_for(state="hidden", timeout=10000)
            self.check(self.detail)
            return root.evaluate(CARD_SCRIPT)
        except AccessBlocked:
            raise
        except Exception as error:
            self.check(self.detail)
            raise AccessBlocked("not_ready", "正文未完整加载或无法展开；已保存前面的材料。") from error

    def more(self):
        before = self.page.locator(self.selector).count()
        self.page.keyboard.press("End")
        try:
            self.page.wait_for_function("p=>document.querySelectorAll(p.selector).length>p.before", arg=dict(selector=self.selector, before=before), timeout=12000)
            self.check(self.page)
            return "more"
        except Exception:
            self.check(self.page)
            return "stalled"


def run_edge(target, max_items=20, max_pages=3, kinds=None, resume=True):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as error:
        raise AccessBlocked("setup_required", "请安装 requirements-edge.txt。") from error
    if not (PROFILE / "Default").is_dir():
        raise AccessBlocked("needs_login", "请先运行 python scripts/zhihu-edge.py login 登录专用 Edge。")
    kinds = kinds or ["answer", "article"]
    target = normalize_target(target)
    checkpoint = Checkpoint(ROOT / f".local/zhihu/checkpoints/{target}-{'-'.join(kinds)}.json", target, kinds) if resume else None
    with sync_playwright() as playwright:
        try:
            context = playwright.chromium.launch_persistent_context(str(PROFILE), channel="msedge", headless=False, chromium_sandbox=True)
        except Exception as error:
            raise AccessBlocked("browser_unavailable", "专用 Edge 无法启动或仍被登录窗口占用；请关闭专用窗口后重试。") from error
        try:
            return collect_dom_history(EdgeDOMReader(context), target, max_items, max_pages, kinds, checkpoint)
        finally:
            context.close()


def collect_edge_process(target, max_items=20, max_pages=3, kinds=None):
    try:
        process = subprocess.run(
            [os.getenv("ZHIHU_EDGE_PYTHON") or sys.executable, str(Path(__file__).with_name("edge_worker.py"))],
            input=json.dumps(dict(target=normalize_target(target), max_items=max_items, max_pages=max_pages, kinds=kinds)),
            capture_output=True, text=True, encoding="utf-8", timeout=900,
        )
        payload = json.loads(process.stdout)
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        raise AccessBlocked("collector_unavailable", "Edge工作器未完成；断点保留，不自动重试。") from error
    if not payload.get("ok"):
        raise AccessBlocked(payload.get("code", "collector_error"), payload.get("message", "Edge采集失败。"), payload.get("partial"))
    if not isinstance(payload.get("data"), dict):
        raise ValueError("Edge工作器返回格式无效。")
    return payload["data"]
