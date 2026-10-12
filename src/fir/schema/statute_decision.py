from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Literal
from pydantic import BaseModel, Field

def _statute_index():
    try:
        from fir.statute.statute_text import StatuteIndex
        return StatuteIndex.load()
    except FileNotFoundError:
        return None

class SectionSuggestion(BaseModel):
    bns_section: str
    ipc_section: str = Field(description='the IPC section it was converted from')
    offence: str = ''
    cognizable: Literal['cognizable', 'non_cognizable', 'conditional', 'unknown'] = 'unknown'
    map_confidence: str = ''
    notes: str = ''
    statute_text: str | None = Field(default=None, description='the words of the (IPC) section, so the officer reads the law, not a number')
    bns_heading: str | None = Field(default=None, description='marginal heading of the BNS section (gazette)')
    bns_text: str | None = Field(default=None, description='operative words of the BNS section or sub-section proposed -- the law the officer files under; the IPC text above is training-label lineage')
    retrieval_rank: int | None = Field(default=None, description='1-based rank of this section when the statute texts are retrieved against the narrative; a low rank corroborates the classifier, None means no lexical overlap at all')

class ReviewFlag(BaseModel):
    ipc_section: str
    reason: str
    offence: str = ''
    suggested_bns: str | None = None
    confidence: str | None = None
    notes: str = ''
    statute_text: str | None = None
    bns_heading: str | None = None
    bns_text: str | None = None

class CueHit(BaseModel):
    ipc_section: str
    suggested_bns: str | None = None
    offence: str = ''
    cognizable: Literal['cognizable', 'non_cognizable', 'conditional', 'unknown'] = 'unknown'
    evidenced: int = 0
    total: int = 0
    cues: list[str] = Field(default_factory=list)

class StatuteDecision(BaseModel):
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    classifier: str = ''
    source: Literal['audio', 'text'] = 'text'
    narrative: str = ''
    transcript: str | None = None
    asr_language: str | None = None
    asr_flags: list[str] = Field(default_factory=list, description='fir.asr.quality flags; a repetition loop or foreign-script drift means the transcript may contain words the complainant never said')
    predicted_ipc: list[str] = Field(default_factory=list)
    ipc_top_k: list[tuple[str, float]] = Field(default_factory=list)
    suggested_sections: list[SectionSuggestion] = Field(default_factory=list)
    review_flags: list[ReviewFlag] = Field(default_factory=list)
    cue_hits: list[CueHit] = Field(default_factory=list, description='sections evidenced in the original text but not predicted -- the recall safety net')
    route: Literal['FIR', 'CSR', 'OFFICER_REVIEW'] = 'OFFICER_REVIEW'
    rationale: str = ''
    errors: list[str] = Field(default_factory=list)

    @property
    def requires_officer_action(self) -> bool:
        return True

    @property
    def is_auto_resolvable(self) -> bool:
        return not self.review_flags and (not self.asr_flags) and (self.route in ('FIR', 'CSR'))

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> 'StatuteDecision':
        from fir.statute.bns_text import bns_text
        from fir.statute.cognizability import classify_section
        bns = bns_text()
        cog = state.get('cognizability') or {}
        narrative = state.get('narrative_en') or state.get('narrative', '') or ''
        index = _statute_index()
        suggestions = [SectionSuggestion(bns_section=row['bns_section'] if str(row['bns_section']).upper().startswith('BNS ') else f"BNS {row['bns_section']}", ipc_section=row['ipc_section'], offence=row.get('offence', ''), cognizable=cog.get(row['bns_section'], classify_section(str(row['bns_section'])).value), map_confidence=row.get('confidence', ''), notes=row.get('notes', ''), statute_text=index.text_for(row['ipc_section']) if index else None, bns_heading=bns.heading_for(str(row['bns_section'])) if bns else None, bns_text=bns.text_for(str(row['bns_section'])) if bns else None, retrieval_rank=index.rank_of(narrative, row['ipc_section']) if index and narrative else None) for row in state.get('auto_applied') or []]
        review = [ReviewFlag(**item, statute_text=index.text_for(item['ipc_section']) if index else None, bns_heading=bns.heading_for(item['suggested_bns']) if bns and item.get('suggested_bns') else None, bns_text=bns.text_for(item['suggested_bns']) if bns and item.get('suggested_bns') else None) for item in state.get('review_queue') or []]
        return cls(classifier=state.get('classifier_name', ''), source='audio' if state.get('transcript') else 'text', narrative=state.get('narrative', ''), transcript=state.get('transcript'), asr_language=state.get('asr_language'), asr_flags=list(state.get('asr_flags') or []), predicted_ipc=list(state.get('predicted_ipc') or []), ipc_top_k=list(state.get('ipc_top_k') or []), suggested_sections=suggestions, review_flags=review, cue_hits=[CueHit(**{k: v for k, v in h.items() if k != 'reason'}) for h in state.get('cue_hits') or []], route=state.get('route', 'OFFICER_REVIEW'), rationale=state.get('rationale', ''), errors=list(state.get('errors') or []))
