"""Data contracts shared by collectors, LLM stages, the ledger and the web export."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, computed_field, Field

from radar.scoring import Level, Scores, SolutionClass

EvidenceKind = Literal[
    "buyer_request",      # someone asking for / hiring for a fix
    "budget_or_payment",  # stated budget or actual payment; loss alone is not a buying signal
    "workaround",         # spreadsheets, scripts, manual process, stitching tools together
    "complaint",          # first-hand pain without behavior evidence
    "counterevidence",    # resolved thread, "existing tool is enough", config mistake
    "vendor_reply",       # seller pitching in a thread
    "vendor_launch",      # someone launching a product (supply signal, not demand)
    "official_doc",       # vendor docs / pricing / changelog
    "news",               # surveys, articles, timelines
]

# Only these kinds count toward demand; vendor voices and docs never do (codex-pp independence rule).
DEMAND_KINDS: frozenset[str] = frozenset({"buyer_request", "budget_or_payment", "workaround", "complaint"})

ClusterStatus = Literal["active", "watch", "demoted"]


class RawItem(BaseModel):
    """One public post/comment/issue as fetched, before any judgment."""

    source: str
    external_id: str
    url: str
    title: str
    body: str = ""
    created_at: datetime
    updated_at: datetime | None = None
    resolved: bool | None = None
    score: int = 0
    comments: int = 0
    tags: list[str] = []
    thread: list[str] = []
    refresh_scope: Literal["original_and_replies", "replies_only", "not_revisited"] = "not_revisited"

    @property
    def key(self) -> str:
        return f"{self.source}:{self.external_id}"

    @property
    def revision_key(self) -> str:
        return f"{self.key}@{self.updated_at.isoformat()}" if self.updated_at else self.key


class Evidence(BaseModel):
    url: str
    platform: str
    date: str | None
    date_basis: str
    kind: EvidenceKind
    paraphrase: str
    engagement: str
    source_key: str = ""

    @computed_field
    @property
    def counts_as_demand(self) -> bool:
        return self.kind in DEMAND_KINDS


class ScoreEvent(BaseModel):
    run_id: str
    date: str
    overall: float
    reason: str


class Cluster(BaseModel):
    id: str
    name: str
    short_title: str = Field(default="", max_length=32)
    status: ClusterStatus
    status_reason: str = ""
    industry: str = ""
    who: str = ""
    problem: str = ""
    solution_class: SolutionClass | None = None
    pain_confidence: Level | None = None
    gap_confidence: Level | None = None
    scores: Scores | None = None
    evidence: list[Evidence] = []
    workaround: str = ""
    existing_solutions: list[str] = []
    why_insufficient: str = ""
    root_cause: str = ""
    why_now: str = ""
    opportunity_hypothesis: str = ""
    contrarian: list[str] = []
    next_validation: list[str] = []
    watch_next: str = ""
    first_detected: str
    last_detected: str
    detected_runs: int = 1
    score_history: list[ScoreEvent] = []
    origin: list[str] = []
    solution_checked_at: str | None = None
    buyer: str = ""
    payment_evidence: str = ""
    current_cost: str = ""
    buying_evidence_urls: list[str] = []


class Signal(BaseModel):
    """Emerging signal: worth watching, not yet a cluster."""

    id: str
    title: str
    why_watch: str
    watch_next: str = ""
    evidence: list[Evidence] = []
    first_detected: str
    last_detected: str
    detected_runs: int = 1
    origin: list[str] = []
    status: Literal["watching", "promoted", "dropped"] = "watching"
    promoted_to: str | None = None


class MergeRecord(BaseModel):
    """Where each cluster from the three original agent runs ended up."""

    origin: str
    old_id: str
    old_name: str
    new_id: str
    action: Literal["merged", "kept", "watch", "demoted", "signal", "excluded"]
    reason: str


class Ledger(BaseModel):
    schema_version: int = 1
    updated_at: datetime
    last_run_id: str | None = None
    clusters: list[Cluster]
    signals: list[Signal]
    merge_log: list[MergeRecord] = []


class SourceStat(BaseModel):
    source: str
    fetched: int = 0
    new: int = 0
    prefiltered: int = 0
    selected: int | None = None
    analyzed: int | None = None
    demand_signals: int | None = None
    buying_signals: int | None = None
    counter_signals: int | None = None
    warnings: list[str] = []
    degraded: bool = False
    error: str | None = None


class UsageRecord(BaseModel):
    stage: str
    provider: str = ""
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    web_search_requests: int = 0
    cost_usd: float = 0.0


class ClusterChange(BaseModel):
    cluster_id: str
    action: Literal["created", "updated"]
    overall_before: float | None
    overall_after: float
    reason: str


class RunReport(BaseModel):
    run_id: str
    started_at: datetime
    finished_at: datetime | None = None
    window_hours: int
    sources: list[SourceStat] = []
    triaged: int = 0
    kept: int = 0
    changes: list[ClusterChange] = []
    new_signals: list[str] = []
    top_opportunities: list[str] = []
    summary: str = ""
    usage: list[UsageRecord] = []
    notes: list[str] = []
    status: Literal["success", "partial", "failed"] = "success"


# ---- LLM structured outputs -------------------------------------------------


class TriageVerdict(BaseModel):
    key: str
    is_pain_point: bool
    codable: bool
    who: str
    pain: str
    loss: str
    workaround: str
    kind: EvidenceKind
    reject_reason: str
    needs_context: bool = False


class TriageResult(BaseModel):
    verdicts: list[TriageVerdict]


class ClusterUpdate(BaseModel):
    """`cluster_id` is an existing ledger id, or "NEW". Empty strings/lists mean "keep what the ledger has"."""

    cluster_id: str
    name: str
    short_title: str = Field(default="", max_length=32)
    who: str
    problem: str
    industry: str
    workaround: str
    existing_solutions: list[str]
    why_insufficient: str
    root_cause: str
    why_now: str
    opportunity_hypothesis: str
    contrarian: list[str]
    next_validation: list[str]
    new_evidence: list[Evidence]
    solution_class: SolutionClass
    scores: Scores
    score_reason: str
    pain_confidence: Level
    gap_confidence: Level
    buyer: str = ""
    payment_evidence: str = ""
    current_cost: str = ""
    buying_evidence_urls: list[str] = []


class SignalDraft(BaseModel):
    title: str
    why_watch: str
    watch_next: str
    evidence: list[Evidence]


class SignalUpdate(BaseModel):
    signal_id: str
    status: Literal["watching", "promoted", "dropped"]
    cluster_id: str = ""
    why_watch: str
    watch_next: str
    evidence: list[Evidence]


class AnalysisResult(BaseModel):
    updates: list[ClusterUpdate]
    new_signals: list[SignalDraft]
    top_opportunity_ids: list[str]
    summary: str
    signal_updates: list[SignalUpdate] = []


class SolutionCheck(BaseModel):
    existing_solutions: list[str]
    why_insufficient: str
    solution_class: SolutionClass
    sources: list[Evidence]
