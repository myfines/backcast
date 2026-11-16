"""Deterministic eligibility gates surrounding model-assisted interpretation."""

from datetime import datetime, timezone

LABELS = {
    "correct": "正确",
    "wrong": "错误",
    "partial": "部分正确",
    "insufficient": "证据不足",
    "pending": "尚未到期",
    "unverifiable": "不可验证",
}


def timestamp(value):
    if not value:
        return None
    try:
        d = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def validate_citations(citations, evidence):
    allowed = {e["id"] for e in evidence if e.get("verified")}
    if (
        not isinstance(citations, list)
        or not citations
        or any(not isinstance(c, str) or c not in allowed for c in citations)
    ):
        raise ValueError("引用缺失或不属于已抓取的证据，拒绝生成结论。")


def decide(claim, evidence, proposal=None, now=None):
    current = timestamp(now) if now else datetime.now(timezone.utc)
    deadline, published, edited = (
        timestamp(claim.get(k)) for k in ("deadline", "published_at", "edited_at")
    )
    status, reason, citations = "insufficient", "尚无足够的外部证据。", []
    if claim.get("kind") == "opinion":
        status, reason = "unverifiable", "主观判断缺少客观检验标准。"
    elif claim.get("kind") == "prediction" and not deadline:
        status, reason = "unverifiable", "预测没有明确截止日期，不能擅自补充窗口。"
    elif deadline and deadline > current:
        status, reason = "pending", "预测窗口尚未结束。"
    elif proposal and evidence:
        status = proposal.get("status", "insufficient")
        if status not in LABELS:
            raise ValueError("模型返回了未知判定。")
        citations = proposal.get("citations", [])
        if citations:
            validate_citations(citations, evidence)
        if status in ("correct", "wrong", "partial"):
            usable = [
                e
                for e in evidence
                if not timestamp(e.get("published_at")) or timestamp(e["published_at"]) <= current
            ]
            validate_citations(citations, usable)
        reason = proposal.get("reason", "请查看证据与核验口径。")
        if not isinstance(reason, str):
            raise ValueError("判定理由必须是文本。")
    outcome = timestamp(claim.get("outcome_at"))
    boundary = min(t for t in (deadline, outcome) if t) if deadline or outcome else None
    eligible = bool(
        claim.get("kind") == "prediction"
        and published
        and deadline
        and boundary
        and published < boundary
        and claim.get("original_version_verified")
        and (not edited or edited < boundary)
        and status in ("correct", "wrong", "partial")
    )
    qualification = (
        "时间与版本满足计分条件。"
        if eligible
        else "未满足严格计分条件；结果复盘不等于已证明预测能力。"
    )
    return dict(
        status=status,
        reason=reason,
        citations=citations,
        eligible=eligible,
        qualification=qualification,
    )


def statistics(verdicts):
    scored = [
        v for v in verdicts if v.get("eligible") and v["status"] in ("correct", "wrong", "partial")
    ]
    correct = sum(v["status"] == "correct" for v in scored)
    return dict(
        total=len(verdicts),
        effective=len(scored),
        correct=correct,
        partial=sum(v["status"] == "partial" for v in scored),
        accuracy=round(correct / len(scored) * 100) if scored else None,
    )
