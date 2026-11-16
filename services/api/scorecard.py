"""Explainable forecast track records, not personality or integrity scores.

Independent implementation of standard Brier / Wilson formulae. See
docs/OPEN_SOURCE_RESEARCH.md for design references and explicit differences.
"""

from collections import Counter
from datetime import datetime, timezone
import math
from urllib.parse import urlsplit, urlunsplit
from .rules import timestamp

METHOD_VERSION = "backcast-track-record-v1"
POLICY = {
    "minimum_events": 20,
    "minimum_span_days": 180,
    "minimum_active_months": 3,
    "minimum_paired_events": 10,
    "calibration_bins": 5,
}


def wilson_interval(successes: int, n: int):
    """95% Wilson interval for exact categorical success, including small N."""
    if not n:
        return None
    z = 1.959963984540054
    p = successes / n
    denominator = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denominator
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denominator
    return [round(max(0, center - margin), 6), round(min(1, center + margin), 6)]


def canonical_origin(url):
    try:
        u = urlsplit(url)
        if u.scheme not in ("http", "https") or not u.hostname:
            return None
        return urlunsplit((u.scheme.lower(), u.netloc.lower(), u.path.rstrip("/"), "", ""))
    except ValueError:
        return None


def _probability_record(c):
    p = c.get("probability")
    outcome = c.get("binary_outcome")
    return (
        c.get("forecast_format") == "probabilistic"
        and type(p) in (int, float)
        and math.isfinite(p)
        and 0 <= p <= 1
        and type(outcome) in (int, bool)
        and outcome in (0, 1)
    )


def eligibility_reasons(c, current):
    """Recompute all gates; never trust a persisted `eligible=True` alone."""
    reasons = []
    published, deadline, event, edited = (
        timestamp(c.get(k)) for k in ("published_at", "deadline", "outcome_at", "edited_at")
    )
    if c.get("kind") != "prediction":
        reasons.append("not_prediction")
    if not c.get("event_key"):
        reasons.append("unidentified_event")
    if not c.get("original_version_verified"):
        reasons.append("unverified_original")
    if not published or not deadline:
        reasons.append("missing_time")
    if deadline and deadline > current:
        reasons.append("not_due")
    boundary = min(t for t in (deadline, event) if t) if deadline or event else None
    if published and boundary and published >= boundary:
        reasons.append("not_before_event")
    if edited and boundary and edited >= boundary:
        reasons.append("late_edit")
    if event and event > current:
        reasons.append("future_outcome")
    verdict = c.get("verdict", {})
    evidence = {e["id"]: e for e in c.get("evidence", []) if e.get("id")}
    citations = verdict.get("citations", [])
    if not citations:
        reasons.append("no_citations")
    for id in citations:
        e = evidence.get(id)
        if not e or not e.get("verified") or not canonical_origin(e.get("url", "")):
            reasons.append("invalid_citation")
            continue
        date = timestamp(e.get("published_at"))
        if not date:
            reasons.append("undated_evidence")
        elif date > current:
            reasons.append("future_evidence")
    if c.get("forecast_format") == "probabilistic":
        if not _probability_record(c):
            reasons.append("invalid_probability_or_outcome")
    elif verdict.get("status") not in ("correct", "wrong", "partial"):
        reasons.append("unresolved")
    return list(dict.fromkeys(reasons))


def _records(claims, domain, current):
    available = [
        c
        for c in claims
        if (domain is None or c.get("domain") == domain)
        and (not timestamp(c.get("published_at")) or timestamp(c.get("published_at")) <= current)
    ]
    # Earliest statement per event wins even when it is unresolved or a later version is better.
    groups = {}
    unidentified = []
    for c in sorted(
        available,
        key=lambda c: (
            timestamp(c.get("published_at")) or datetime.max.replace(tzinfo=timezone.utc),
            c["id"],
        ),
    ):
        key = c.get("event_key")
        if key:
            groups.setdefault(key, c)
        else:
            unidentified.append(c)
    unique = list(groups.values()) + unidentified
    reasons = {c["id"]: eligibility_reasons(c, current) for c in unique}
    return available, groups, [c for c in unique if not reasons[c["id"]]], reasons


def build_scorecard(claims, domain=None, as_of=None, sampling_protocol=None, pending_reviews=0):
    current = timestamp(as_of) if as_of else datetime.now(timezone.utc)
    if current is None:
        raise ValueError("as_of 必须是 ISO 日期或带时区时间。")
    available, groups, scored, exclusions = _records(claims, domain, current)
    categorical = [c for c in scored if c.get("forecast_format") != "probabilistic"]
    probabilistic = [c for c in scored if _probability_record(c)]
    counts = Counter(c["verdict"]["status"] for c in categorical)
    n = len(categorical)
    p_n = len(probabilistic)
    brier = (
        sum((c["probability"] - c["binary_outcome"]) ** 2 for c in probabilistic) / p_n
        if p_n
        else None
    )
    calibration = []
    for i in range(POLICY["calibration_bins"]):
        low = i / 5
        high = (i + 1) / 5
        items = [
            c
            for c in probabilistic
            if low <= c["probability"] and (c["probability"] < high or i == 4)
        ]
        calibration.append(
            {
                "lower": low,
                "upper": high,
                "n": len(items),
                "mean_probability": (
                    round(sum(c["probability"] for c in items) / len(items), 6) if items else None
                ),
                "observed_frequency": (
                    round(sum(c["binary_outcome"] for c in items) / len(items), 6)
                    if items
                    else None
                ),
            }
        )
    dates = sorted(
        timestamp(c.get("published_at")) for c in scored if timestamp(c.get("published_at"))
    )
    span = (dates[-1] - dates[0]).days if dates else 0
    months = len({d.strftime("%Y-%m") for d in dates})
    evidence = {}
    for c in available:
        for e in c.get("evidence", []):
            key = canonical_origin(e.get("url", "")) or e.get("id")
            if key:
                evidence[key] = e
    dated = sum(bool(timestamp(e.get("published_at"))) for e in evidence.values())
    originals = sum(bool(c.get("original_version_verified")) for c in available)
    confirmed_origins = {
        canonical_origin(e.get("origin_url", ""))
        for e in evidence.values()
        if e.get("origin_confirmed")
    }
    confirmed_origins.discard(None)
    primary = sum(
        e.get("source_type") == "primary" and bool(e.get("origin_confirmed"))
        for e in evidence.values()
    )
    enough = (
        len(scored) >= POLICY["minimum_events"]
        and span >= POLICY["minimum_span_days"]
        and months >= POLICY["minimum_active_months"]
    )
    sampling_confirmed = False
    if (
        sampling_protocol
        and sampling_protocol.get("complete")
        and sampling_protocol.get("method") == "complete_window"
    ):
        start, end = timestamp(sampling_protocol.get("start")), timestamp(
            sampling_protocol.get("end")
        )
        observed_domains = {c.get("domain") for c in available}
        sampling_confirmed = bool(
            start
            and end
            and start < end
            and dates
            and all(start <= d <= end for d in dates)
            and observed_domains == {sampling_protocol.get("domain")}
        )
    warnings = []
    if len(scored) < POLICY["minimum_events"]:
        warnings.append("有效独立事件不足 20 个，不据此推荐专家。")
    if span < POLICY["minimum_span_days"]:
        warnings.append("有效样本发表跨度不足 180 天。")
    if months < POLICY["minimum_active_months"]:
        warnings.append("有效样本不足 3 个活跃月份。")
    if not sampling_confirmed:
        warnings.append("采样覆盖未经确认，不能排除只挑成功案例。")
    if pending_reviews:
        warnings.append("存在待处理纠错；排名资格暂停。")
    if p_n and p_n < 20:
        warnings.append("概率样本过少；Brier 仅作记录，校准分箱不可用于稳定能力推断。")
    return {
        "method_version": METHOD_VERSION,
        "as_of": current.isoformat(),
        "domain": domain,
        "coverage": {
            "total_claims": len(available),
            "independent_events": len(groups),
            "scored_events": len(scored),
            "duplicate_records": max(0, len(available) - len(exclusions)),
            "span_days": span,
            "active_months": months,
            "sampling_confirmed": sampling_confirmed,
        },
        "categorical": {
            "n": n,
            "correct": counts["correct"],
            "wrong": counts["wrong"],
            "partial": counts["partial"],
            "accuracy": round(counts["correct"] / n, 6) if n else None,
            "wilson_95": wilson_interval(counts["correct"], n),
        },
        "probabilistic": {
            "n": p_n,
            "brier": round(brier, 6) if brier is not None else None,
            "skill_vs_50pct": round(1 - brier / 0.25, 6) if brier is not None else None,
            "baseline_brier": 0.25,
            "calibration": calibration,
        },
        "evidence_quality": {
            "evidence_count": len(evidence),
            "dated_evidence_ratio": round(dated / len(evidence), 6) if evidence else None,
            "verified_original_ratio": round(originals / len(available), 6) if available else None,
            "confirmed_origins": len(confirmed_origins),
            "confirmed_primary_sources": primary,
        },
        "readiness": {
            "level": "sufficient_samples" if enough else "insufficient",
            "eligible_for_ranking": enough and sampling_confirmed and pending_reviews == 0,
            "pending_reviews": pending_reviews,
            "policy": POLICY.copy(),
            "warnings": warnings,
        },
        "exclusions": dict(
            Counter(reason for reasons in exclusions.values() for reason in reasons)
        ),
        "limitations": [
            "评价的是特定领域的历史判断记录，不是个人诚信或专业资质认证。",
            "50% 是固定中性基线，不是题目难度调整或市场共识。",
            "as_of 过滤原文、结果与证据时间，不重放历史数据库或历史复核状态。",
        ],
    }


def compare_forecasters(records_by_author, domain=None, as_of=None, protocols=None, pending=None):
    current = timestamp(as_of) if as_of else datetime.now(timezone.utc)
    if current is None:
        raise ValueError("as_of 必须是 ISO 日期或带时区时间。")
    protocols = protocols or {}
    pending = pending or {}
    reports = {
        id: build_scorecard(items, domain, as_of, protocols.get(id), pending.get(id, 0))
        for id, items in records_by_author.items()
    }
    indexed = {
        id: {
            c["event_key"]: c for c in _records(items, domain, current)[2] if _probability_record(c)
        }
        for id, items in records_by_author.items()
    }
    shared = (
        set.intersection(*(set(index) for index in indexed.values()))
        if len(indexed) >= 2
        else set()
    )
    conflicts = sorted(
        key
        for key in shared
        if len(
            {
                (index[key]["binary_outcome"], timestamp(index[key].get("deadline")))
                for index in indexed.values()
            }
        )
        != 1
    )
    shared -= set(conflicts)
    results = []
    for id, index in indexed.items():
        brier = (
            sum((index[key]["probability"] - index[key]["binary_outcome"]) ** 2 for key in shared)
            / len(shared)
            if shared
            else None
        )
        results.append(
            {
                "author_id": id,
                "paired_brier": round(brier, 6) if brier is not None else None,
                "paired_n": len(shared),
                "scorecard": reports[id],
            }
        )
    comparable = bool(
        domain
        and len(shared) >= POLICY["minimum_paired_events"]
        and all(s["readiness"]["eligible_for_ranking"] for s in reports.values())
    )
    return {
        "method_version": METHOD_VERSION,
        "domain": domain,
        "paired_events": len(shared),
        "event_keys": sorted(shared),
        "conflicting_events": conflicts,
        "comparable": comparable,
        "authors": results,
        "reason": (
            "同领域、共同事件与采样条件满足比较政策。"
            if comparable
            else "仅展示记录；须指定领域、有至少10个同口径共同概率事件，并满足各自样本与覆盖政策，才允许比较排名。"
        ),
    }
