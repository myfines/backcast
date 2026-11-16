"""Frontend-facing API; scoring, review, evidence metadata and async verification."""

import hmac
import json
import os
import re
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Query
from . import store
from .rules import decide, timestamp, validate_citations
from .scorecard import METHOD_VERSION, POLICY, build_scorecard, compare_forecasters
from .schemas import (
    AuthorReport,
    AuthorSummary,
    Claim,
    CompareRequest,
    Comparison,
    CreateAuthor,
    EvidenceMetadata,
    HumanResolution,
    Job,
    Page,
    SamplingProtocol,
    Scorecard,
)


def require_reviewer(x_review_token: str | None = Header(default=None)):
    expected = os.getenv("REVIEW_API_TOKEN", "")
    if not expected:
        raise HTTPException(503, "人工复核未启用；请在后端配置 REVIEW_API_TOKEN。")
    if not x_review_token or not hmac.compare_digest(x_review_token, expected):
        raise HTTPException(403, "人工裁定需要有效的复核令牌。")


def get_author(id):
    author = next((a for a in store.all_authors() if a["id"] == id), None)
    if not author:
        raise HTTPException(404, "作者档案不存在。")
    return author


def get_claim(id):
    claim = next((c for c in store.all_claims() if c["id"] == id), None)
    if not claim:
        raise HTTPException(404, "命题不存在。")
    return claim


def pending_reviews(author_id):
    with store.db() as c:
        return c.execute(
            "SELECT count(*) FROM reviews r JOIN claims c ON c.id=r.claim_id WHERE c.author_id=? AND r.status='pending'",
            (author_id,),
        ).fetchone()[0]


def score(author, claims=None, domain=None, as_of=None):
    items = (
        claims
        if claims is not None
        else [c for c in store.all_claims() if c["author_id"] == author["id"]]
    )
    protocol = author.get("sampling_protocol")
    if protocol and domain and protocol.get("domain") != domain:
        protocol = None
    try:
        return build_scorecard(items, domain, as_of, protocol, pending_reviews(author["id"]))
    except ValueError as e:
        raise HTTPException(422, str(e)) from e


def author_view(author, **options):
    return {**author, "scorecard": score(author, **options)}


def save_updated_claim(c, claim, action, data):
    c.execute(
        "UPDATE claims SET data=? WHERE id=?", (json.dumps(claim, ensure_ascii=False), claim["id"])
    )
    store.audit(c, action, claim["id"], data)


def claim_as_of(claim, current):
    """Reconstruct an evidence-limited view, never expose an outcome from the future."""
    result = json.loads(json.dumps(claim))
    result["evidence"] = [
        e
        for e in result["evidence"]
        if timestamp(e.get("published_at")) and timestamp(e["published_at"]) <= current
    ]
    try:
        verdict = decide(result, result["evidence"], result["verdict"], now=current.isoformat())
    except ValueError:
        verdict = decide(result, [], now=current.isoformat())
    outcome = timestamp(result.get("outcome_at"))
    if outcome and outcome > current:
        verdict = decide({**result, "deadline": outcome.isoformat()}, [], now=current.isoformat())
        result["binary_outcome"] = None
    result["verdict"] = verdict
    return result


def create_router(verify_claim):
    router = APIRouter(prefix="/api/v1", tags=["v1"])

    @router.get("/methodology")
    def methodology():
        return {
            "version": METHOD_VERSION,
            "policy": POLICY,
            "metrics": [
                "exact_accuracy",
                "wilson_95",
                "brier",
                "calibration",
                "traceability",
                "sampling_coverage",
            ],
            "excluded": [
                "人格诚信评分",
                "粉丝数和点赞加权",
                "从语气猜测概率",
                "不同题目集合的直接排名",
            ],
            "references": [
                "https://github.com/Metaculus/metaculus",
                "https://github.com/forecastingresearch/forecastbench",
                "https://github.com/Metaculus/forecasting-tools",
                "https://github.com/ericrisco/rsc-harness",
            ],
            "details": "docs/OPEN_SOURCE_RESEARCH.md",
        }

    @router.get("/authors", response_model=Page[AuthorSummary])
    def authors(
        q: str = "",
        domain: str | None = None,
        followed: bool | None = None,
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        items = [
            a
            for a in store.all_authors()
            if (domain is None or a["domain"] == domain)
            and (followed is None or a["followed"] == followed)
            and (
                not q
                or q.casefold()
                in " ".join(
                    [a["name"], a.get("english", ""), a["role"], *a.get("tags", [])]
                ).casefold()
            )
        ]
        return {
            "items": [author_view(a) for a in items[offset : offset + limit]],
            "total": len(items),
            "limit": limit,
            "offset": offset,
        }

    @router.post("/authors", response_model=AuthorSummary, status_code=201)
    def create_author(body: CreateAuthor):
        aid = str(uuid4())
        author = dict(
            id=aid,
            name=body.name,
            domain=body.domain,
            role=body.role,
            bio=body.bio,
            english="",
            initials=body.name[:2],
            color="#e0e7df",
            type="待确认",
            tags=[],
            highlight="从历史判断建立档案",
            takeaway="身份与样本尚待核实。",
            started="未知",
            platform_url=str(body.platform_url) if body.platform_url else None,
        )
        with store.db() as c:
            c.execute(
                "INSERT INTO authors VALUES (?,?)", (aid, json.dumps(author, ensure_ascii=False))
            )
            store.audit(c, "author_created", aid, author)
        return author_view(get_author(aid))

    @router.get("/authors/{author_id}", response_model=AuthorSummary)
    def author(author_id: str):
        return author_view(get_author(author_id))

    @router.get("/authors/{author_id}/scorecard", response_model=Scorecard)
    def scorecard(author_id: str, domain: str | None = None, as_of: str | None = None):
        return score(get_author(author_id), domain=domain, as_of=as_of)

    @router.get("/authors/{author_id}/report", response_model=AuthorReport)
    def report(author_id: str, domain: str | None = None, as_of: str | None = None):
        author = get_author(author_id)
        claims = [
            c
            for c in store.all_claims()
            if c["author_id"] == author_id and (domain is None or c.get("domain") == domain)
        ]
        current = timestamp(as_of) if as_of else datetime.now(timezone.utc)
        if current is None:
            raise HTTPException(422, "as_of 格式无效。")
        claims = [
            c
            for c in claims
            if not timestamp(c.get("published_at")) or timestamp(c["published_at"]) <= current
        ]
        card = score(author, claims, domain, as_of)
        if as_of:
            claims = [claim_as_of(claim, current) for claim in claims]
        with store.db() as c:
            count = c.execute(
                "SELECT count(*) FROM sources WHERE author_id=?", (author_id,)
            ).fetchone()[0]
        return {
            "author": {**author, "scorecard": card},
            "scorecard": card,
            "claims": claims,
            "source_count": count,
            "generated_at": store.utcnow(),
        }

    @router.put(
        "/authors/{author_id}/sampling",
        response_model=AuthorSummary,
        dependencies=[Depends(require_reviewer)],
    )
    def sampling(author_id: str, body: SamplingProtocol):
        author = get_author(author_id)
        start, end = timestamp(body.start), timestamp(body.end)
        if not start or not end or start >= end:
            raise HTTPException(422, "采样窗口无效。")
        if body.domain != author["domain"]:
            raise HTTPException(422, "采样领域必须与档案主领域一致。")
        author["sampling_protocol"] = body.model_dump(mode="json")
        with store.db() as c:
            c.execute(
                "UPDATE authors SET data=? WHERE id=?",
                (json.dumps(author, ensure_ascii=False), author_id),
            )
            store.audit(c, "sampling_reviewed", author_id, author["sampling_protocol"])
        return author_view(author)

    @router.get("/claims", response_model=Page[Claim])
    def claims(
        author_id: str | None = None,
        domain: str | None = None,
        status: str | None = None,
        q: str = "",
        limit: int = Query(20, ge=1, le=100),
        offset: int = Query(0, ge=0),
    ):
        items = [
            c
            for c in store.all_claims()
            if (author_id is None or c["author_id"] == author_id)
            and (domain is None or c.get("domain") == domain)
            and (status is None or c["verdict"]["status"] == status)
            and (not q or q.casefold() in (c.get("title", "") + c.get("text", "")).casefold())
        ]
        return {
            "items": items[offset : offset + limit],
            "total": len(items),
            "limit": limit,
            "offset": offset,
        }

    @router.get("/claims/{claim_id}", response_model=Claim)
    def claim(claim_id: str):
        return get_claim(claim_id)

    @router.get("/claims/{claim_id}/audit", response_model=Page[dict])
    def audit(claim_id: str, limit: int = Query(20, ge=1, le=100), offset: int = Query(0, ge=0)):
        get_claim(claim_id)
        with store.db() as c:
            total = c.execute(
                "SELECT count(*) FROM audits WHERE record_id=?", (claim_id,)
            ).fetchone()[0]
            rows = [
                dict(r)
                for r in c.execute(
                    "SELECT * FROM audits WHERE record_id=? ORDER BY id DESC LIMIT ? OFFSET ?",
                    (claim_id, limit, offset),
                )
            ]
        for row in rows:
            row["data"] = json.loads(row["data"])
        return {"items": rows, "total": total, "limit": limit, "offset": offset}

    @router.get("/sources/{source_id}")
    def source(source_id: str):
        with store.db() as c:
            row = c.execute("SELECT * FROM sources WHERE id=?", (source_id,)).fetchone()
        if not row:
            raise HTTPException(404, "原始材料不存在。")
        return {"id": source_id, "author_id": row["author_id"], **json.loads(row["data"])}

    @router.post("/compare", response_model=Comparison)
    def compare(body: CompareRequest):
        if len(set(body.author_ids)) != len(body.author_ids):
            raise HTTPException(422, "请选择不同的作者。")
        authors = {id: get_author(id) for id in body.author_ids}
        claims = store.all_claims()
        try:
            return compare_forecasters(
                {id: [c for c in claims if c["author_id"] == id] for id in authors},
                body.domain,
                body.as_of,
                {id: a.get("sampling_protocol") for id, a in authors.items()},
                {id: pending_reviews(id) for id in authors},
            )
        except ValueError as e:
            raise HTTPException(422, str(e)) from e

    @router.post(
        "/claims/{claim_id}/resolution",
        response_model=Claim,
        dependencies=[Depends(require_reviewer)],
    )
    def resolve(claim_id: str, body: HumanResolution):
        claim = get_claim(claim_id)
        now = datetime.now(timezone.utc)
        event = timestamp(body.outcome_at)
        if not event or event > now:
            raise HTTPException(422, "结果时间无效或尚未发生。")
        try:
            validate_citations(body.citations, claim["evidence"])
        except ValueError as e:
            raise HTTPException(422, str(e)) from e
        if body.original_version_confirmed:
            snapshot = timestamp(body.original_snapshot_at)
            published = timestamp(claim.get("published_at"))
            deadline = timestamp(claim.get("deadline"))
            if (
                not body.original_snapshot_url
                or not snapshot
                or not published
                or not deadline
                or not published <= snapshot < min(event, deadline)
            ):
                raise HTTPException(
                    422, "确认事前版本需要原始快照链接和先于事件及截止日的快照时间。"
                )
        if body.forecast_format == "probabilistic":
            quote = body.probability_quote
            if (
                body.probability is None
                or body.binary_outcome is None
                or not quote
                or quote not in claim["text"]
            ):
                raise HTTPException(422, "概率预测需要原文中的概率摘录和明确的二元结果。")
            percentages = [
                float(s) / 100 for s in re.findall(r"(?<![\d.])(\d+(?:\.\d+)?)\s*[%％]", quote)
            ]
            if not any(abs(p - body.probability) < 1e-9 for p in percentages):
                raise HTTPException(422, "概率值必须与摘录中的百分数一致，不能由语气推测。")
        before = json.loads(json.dumps(claim))
        claim.update(
            event_key=body.event_key,
            outcome_at=body.outcome_at,
            original_version_verified=body.original_version_confirmed,
            original_snapshot_url=(
                str(body.original_snapshot_url) if body.original_snapshot_url else None
            ),
            original_snapshot_at=body.original_snapshot_at,
            forecast_format=body.forecast_format,
            probability=body.probability,
            binary_outcome=body.binary_outcome,
            probability_quote=body.probability_quote,
        )
        proposal = {
            "status": body.status if body.forecast_format == "categorical" else "insufficient",
            "reason": body.reason,
            "citations": body.citations,
        }
        claim["verdict"] = decide(claim, claim["evidence"], proposal)
        if body.forecast_format == "probabilistic":
            claim["verdict"].update(
                eligible=False, qualification="显式概率预测按 Brier 与校准评估，不计入普通命中率。"
            )
        claim["verdict"].update(reviewed_by=body.reviewer, reviewed_at=store.utcnow())
        with store.db() as c:
            save_updated_claim(
                c,
                claim,
                "manual_resolution",
                {"before": before, "after": claim, "reviewer": body.reviewer},
            )
            c.execute(
                "INSERT INTO verdicts(claim_id,data,created_at) VALUES (?,?,?)",
                (claim_id, json.dumps(claim["verdict"], ensure_ascii=False), store.utcnow()),
            )
            c.execute("UPDATE reviews SET status='resolved' WHERE claim_id=?", (claim_id,))
        return claim

    @router.patch(
        "/evidence/{evidence_id}/metadata",
        response_model=Claim,
        dependencies=[Depends(require_reviewer)],
    )
    def evidence_metadata(evidence_id: str, body: EvidenceMetadata):
        claim = next(
            (c for c in store.all_claims() if any(e["id"] == evidence_id for e in c["evidence"])),
            None,
        )
        if not claim:
            raise HTTPException(404, "当前证据不存在；历史证据不可原地改写。")
        if body.published_at and not timestamp(body.published_at):
            raise HTTPException(422, "证据日期无效。")
        if body.origin_confirmed and not body.origin_url:
            raise HTTPException(422, "确认同源关系需要原始出处 URL。")
        target = next(e for e in claim["evidence"] if e["id"] == evidence_id)
        before = target.copy()
        target.update(
            published_at=body.published_at,
            origin_url=str(body.origin_url) if body.origin_url else None,
            origin_confirmed=body.origin_confirmed,
            source_type=body.source_type,
        )
        with store.db() as c:
            save_updated_claim(
                c,
                claim,
                "evidence_metadata_reviewed",
                {
                    "before": before,
                    "after": target,
                    "reviewer": body.reviewer,
                    "reason": body.reason,
                },
            )
            c.execute(
                "UPDATE evidence SET data=? WHERE id=?",
                (json.dumps(target, ensure_ascii=False), evidence_id),
            )
        return claim

    async def execute_job(id, claim_id):
        with store.db() as c:
            job = json.loads(
                c.execute("SELECT data FROM jobs WHERE id=?", (id,)).fetchone()["data"]
            )
            job.update(status="running", updated_at=store.utcnow())
            c.execute(
                "UPDATE jobs SET data=? WHERE id=?", (json.dumps(job, ensure_ascii=False), id)
            )
        try:
            result = await verify_claim(claim_id)
            job.update(status="succeeded", result=result, error=None, updated_at=store.utcnow())
        except HTTPException as e:
            job.update(status="failed", error=str(e.detail), updated_at=store.utcnow())
        except Exception:
            job.update(
                status="failed", error="核验任务失败；未产生新结论。", updated_at=store.utcnow()
            )
        with store.db() as c:
            c.execute(
                "UPDATE jobs SET data=? WHERE id=?", (json.dumps(job, ensure_ascii=False), id)
            )
            store.audit(
                c, "verification_job_finished", claim_id, {"job_id": id, "status": job["status"]}
            )

    @router.post("/claims/{claim_id}/verification-jobs", response_model=Job, status_code=202)
    def verification_job(claim_id: str, background_tasks: BackgroundTasks):
        get_claim(claim_id)
        id = str(uuid4())
        now = store.utcnow()
        job = {
            "id": id,
            "claim_id": claim_id,
            "status": "queued",
            "created_at": now,
            "updated_at": now,
            "result": None,
            "error": None,
        }
        with store.db() as c:
            c.execute("BEGIN IMMEDIATE")
            # One active verification per claim, preventing duplicate AI spend on retries.
            for row in c.execute("SELECT data FROM jobs WHERE claim_id=?", (claim_id,)):
                active = json.loads(row["data"])
                if active["status"] in ("queued", "running"):
                    return active
            c.execute(
                "INSERT INTO jobs VALUES (?,?,?)",
                (id, claim_id, json.dumps(job, ensure_ascii=False)),
            )
        background_tasks.add_task(execute_job, id, claim_id)
        return job

    @router.get("/jobs/{job_id}", response_model=Job)
    def job(job_id: str):
        with store.db() as c:
            row = c.execute("SELECT data FROM jobs WHERE id=?", (job_id,)).fetchone()
        if not row:
            raise HTTPException(404, "任务不存在。")
        return json.loads(row["data"])

    return router
