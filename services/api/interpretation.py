"""Faithful-reading guards; reasoning bonuses never change factual outcomes.

Inspired by Hindsight's separation of forecasts, trends and scenarios. No
technology-adoption thresholds or tolerance bands are imported into this app.
"""

POLICY = "faithful-reading-v1"


def interpret(candidate, source_text):
    mode = candidate.get("mode", "assertion")
    condition_quotes = candidate.get("condition_quotes") or []
    logic = candidate.get("logic") or {}
    quotes = logic.get("quotes") or []
    for quote in condition_quotes + quotes:
        if not isinstance(quote, str) or not quote.strip() or quote not in source_text:
            raise ValueError("条件或逻辑依据不在作者原文中；不能补造前提。")
    state = candidate.get("condition_state", "unknown") if condition_quotes else "unknown"
    status = logic.get("status", "not_assessed")
    if len(set(quotes)) < 2 or not logic.get("reason"):
        status = "not_assessed"
    return dict(
        policy_version=POLICY, mode=mode,
        reading=candidate.get("reading") or candidate.get("quote", ""),
        condition_quotes=condition_quotes, condition_state=state,
        allow_outcome_verdict=mode != "scenario" and (mode != "conditional" or state == "met"),
        penalize_missing_rationale=False,
        logic=dict(status=status, reason=logic.get("reason") if status != "not_assessed" else None,
                   quotes=quotes, bonus_points=1 if status == "coherent" else 0,
                   changes_factual_verdict=False, provenance="model_assessed_original_quotes"),
    )
