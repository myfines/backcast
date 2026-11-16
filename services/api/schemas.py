"""Stable, OpenAPI-exported contracts for the teammate-owned frontend."""

from typing import Generic, Literal, TypeVar
from pydantic import BaseModel, ConfigDict, Field, HttpUrl

VerdictStatus = Literal["correct", "wrong", "partial", "insufficient", "pending", "unverifiable"]
T = TypeVar("T")


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    offset: int
    limit: int


class Coverage(BaseModel):
    total_claims: int
    independent_events: int
    scored_events: int
    duplicate_records: int
    span_days: int
    active_months: int
    sampling_confirmed: bool


class CategoricalMetrics(BaseModel):
    n: int
    correct: int
    wrong: int
    partial: int
    accuracy: float | None
    wilson_95: list[float] | None


class CalibrationBin(BaseModel):
    lower: float
    upper: float
    n: int
    mean_probability: float | None
    observed_frequency: float | None


class ProbabilityMetrics(BaseModel):
    n: int
    brier: float | None
    skill_vs_50pct: float | None
    baseline_brier: float
    calibration: list[CalibrationBin]


class EvidenceQuality(BaseModel):
    evidence_count: int
    dated_evidence_ratio: float | None
    verified_original_ratio: float | None
    confirmed_origins: int
    confirmed_primary_sources: int


class Readiness(BaseModel):
    level: Literal["insufficient", "sufficient_samples"]
    eligible_for_ranking: bool
    pending_reviews: int
    policy: dict[str, int]
    warnings: list[str]


class Scorecard(BaseModel):
    method_version: str
    as_of: str
    domain: str | None
    coverage: Coverage
    categorical: CategoricalMetrics
    probabilistic: ProbabilityMetrics
    evidence_quality: EvidenceQuality
    readiness: Readiness
    exclusions: dict[str, int]
    limitations: list[str]


class AuthorSummary(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    name: str
    domain: str
    role: str
    type: str
    followed: bool
    tags: list[str]
    scorecard: Scorecard


class Evidence(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    url: str
    source: str
    text: str
    published_at: str | None = None
    retrieved_at: str
    verified: bool
    origin_url: str | None = None
    origin_confirmed: bool = False
    source_type: Literal["primary", "secondary", "unknown"] = "unknown"


class Verdict(BaseModel):
    model_config = ConfigDict(extra="allow")
    status: VerdictStatus
    reason: str
    citations: list[str]
    eligible: bool
    qualification: str


class Claim(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    author_id: str
    title: str
    text: str
    kind: Literal["prediction", "fact", "opinion"]
    domain: str
    source_url: str
    source_name: str
    published_at: str | None = None
    edited_at: str | None = None
    deadline: str | None = None
    outcome_at: str | None = None
    original_version_verified: bool
    evidence: list[Evidence]
    verdict: Verdict
    event_key: str | None = None
    forecast_format: Literal["categorical", "probabilistic"] = "categorical"
    probability: float | None = None
    binary_outcome: int | None = None


class CreateAuthor(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    name: str = Field(min_length=1, max_length=100)
    domain: str = Field(min_length=1, max_length=80)
    role: str = Field(default="用户提交 · 身份待核实", max_length=160)
    bio: str = Field(default="", max_length=2000)
    platform_url: HttpUrl | None = None


class CompareRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    author_ids: list[str] = Field(min_length=2, max_length=3)
    domain: str | None = None
    as_of: str | None = None


class ComparedAuthor(BaseModel):
    author_id: str
    paired_brier: float | None
    paired_n: int
    scorecard: Scorecard


class Comparison(BaseModel):
    method_version: str
    domain: str | None
    paired_events: int
    event_keys: list[str]
    conflicting_events: list[str]
    comparable: bool
    authors: list[ComparedAuthor]
    reason: str


class HumanResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["correct", "wrong", "partial", "insufficient"]
    citations: list[str] = Field(min_length=1, max_length=20)
    reason: str = Field(min_length=15, max_length=4000)
    reviewer: str = Field(min_length=1, max_length=100)
    event_key: str = Field(min_length=3, max_length=200)
    outcome_at: str
    original_version_confirmed: bool = False
    original_snapshot_url: HttpUrl | None = None
    original_snapshot_at: str | None = None
    forecast_format: Literal["categorical", "probabilistic"] = "categorical"
    probability: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False, strict=True)
    probability_quote: str | None = Field(default=None, max_length=1000)
    binary_outcome: Literal[0, 1] | None = None


class EvidenceMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")
    published_at: str | None = None
    origin_url: HttpUrl | None = None
    origin_confirmed: bool = False
    source_type: Literal["primary", "secondary", "unknown"] = "unknown"
    reviewer: str = Field(min_length=1, max_length=100)
    reason: str = Field(min_length=10, max_length=2000)


class SamplingProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")
    method: Literal["complete_window"]
    domain: str
    start: str
    end: str
    complete: bool
    source_index_url: HttpUrl
    reviewer: str = Field(min_length=1, max_length=100)
    note: str = Field(min_length=15, max_length=3000)


class Job(BaseModel):
    id: str
    claim_id: str
    status: Literal["queued", "running", "succeeded", "failed"]
    created_at: str
    updated_at: str
    result: dict | None = None
    error: str | None = None


class AuthorReport(BaseModel):
    author: AuthorSummary
    scorecard: Scorecard
    claims: list[Claim]
    source_count: int
    generated_at: str


class ImportResult(BaseModel):
    author_id: str
    source_id: str
    claims: list[Claim]
    mode: Literal["ai", "rules"]
    message: str
