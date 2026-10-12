from __future__ import annotations
from fir.schema.if1 import Cognizability, FirRecord, SectionCandidate
from fir.schema.statute_decision import StatuteDecision
from fir.statute.cognizability import schedule_source
from fir.statute.elements import check_elements
_ROUTE = {'FIR': 'FIR', 'CSR': 'CSR_advisory', 'OFFICER_REVIEW': 'officer_review'}
_HELD_BACK_SCORE = 0.25

def _bare_section(bns: str) -> str:
    s = bns.strip()
    return s[4:].strip() if s.upper().startswith('BNS ') else s

def section_candidates(decision: StatuteDecision) -> list[SectionCandidate]:
    top_k = {sec: score for sec, score in decision.ipc_top_k}
    narrative = decision.narrative or ''
    out: list[SectionCandidate] = []
    for s in decision.suggested_sections:
        out.append(SectionCandidate(act='BNS_2023', section=_bare_section(s.bns_section), description_en=s.offence, score=float(top_k.get(s.ipc_section, 1.0)), cognizable=True if s.cognizable == 'cognizable' else False if s.cognizable == 'non_cognizable' else None, elements=check_elements(s.ipc_section, narrative), ipc_source=s.ipc_section, mapping_ambiguous=False))
    for f in decision.review_flags:
        if not f.suggested_bns or not f.suggested_bns.upper().startswith('BNS '):
            continue
        out.append(SectionCandidate(act='BNS_2023', section=_bare_section(f.suggested_bns), description_en=f.offence, score=min(_HELD_BACK_SCORE, float(top_k.get(f.ipc_section, _HELD_BACK_SCORE))), cognizable=None, ipc_source=f.ipc_section, mapping_ambiguous=True))
    out.sort(key=lambda c: (-c.score, c.mapping_ambiguous, c.section))
    return out

def cognizability_block(decision: StatuteDecision) -> Cognizability:
    classes = {s.cognizable for s in decision.suggested_sections}
    if not decision.suggested_sections:
        cls = 'undetermined'
    elif classes == {'cognizable'}:
        cls = 'cognizable'
    elif classes == {'non_cognizable'}:
        cls = 'non_cognizable'
    elif classes <= {'unknown', 'conditional'}:
        cls = 'undetermined'
    else:
        cls = 'mixed'
    return Cognizability(decision=cls, route=_ROUTE.get(decision.route, 'officer_review'), schedule_ref=schedule_source(), rationale=decision.rationale)

def apply_decision(record: FirRecord, decision: StatuteDecision) -> FirRecord:
    record.acts_sections = section_candidates(decision)
    record.cognizability = cognizability_block(decision)
    if record.cognizability.route == 'CSR_advisory':
        record.status = 'csr_advisory'
    elif record.status == 'csr_advisory':
        record.status = 'draft'
    if decision.transcript is not None:
        record.information_type = 'oral'
    return record

def record_from_decision(decision: StatuteDecision) -> FirRecord:
    return apply_decision(FirRecord(), decision)
