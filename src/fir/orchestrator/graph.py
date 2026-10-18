from __future__ import annotations
from dataclasses import asdict
from typing import Annotated, Any, Protocol, TypedDict, runtime_checkable
from langgraph.graph import END, START, StateGraph
from fir.statute.cognizability import Route, route_case
from fir.statute.ipc_bns_map import IpcBnsMap

@runtime_checkable
class StatuteClassifier(Protocol):
    name: str

    def predict_sections(self, text: str, threshold: float | None=...) -> list[str]:
        ...

    def top_k(self, text: str, k: int=...) -> list[tuple[str, float]]:
        ...

def _keep_last(_old: Any, new: Any) -> Any:
    return new

def _extend(old: list, new: list) -> list:
    return (old or []) + (new or [])

class SliceState(TypedDict, total=False):
    audio_path: str
    narrative: str
    provided_translation_en: str
    reference_transcript: str
    transcript: str
    asr_language: str
    asr_duration: float
    asr_device: str
    asr_flags: list[str]
    predicted_ipc: list[str]
    ipc_top_k: list[tuple[str, float]]
    classifier_name: str
    bns_sections: list[str]
    auto_applied: list[dict]
    review_queue: list[dict]
    cue_hits: list[dict]
    route: str
    cognizability: dict
    rationale: str
    extracted_spans: list[dict]
    narrative_en: str
    translation: dict
    fir_record: dict
    if1_text: str
    fill_report: dict
    narrative_grounded: bool
    evidence_graph: dict
    clarification_questions: list[dict]
    errors: Annotated[list[str], _extend]

def make_asr_node(asr: Any):

    def asr_node(state: SliceState) -> dict:
        path = state.get('audio_path')
        if not path:
            return {}
        if asr is None:
            return {'errors': ['asr_node: no ASR backend configured']}
        try:
            tr = asr.transcribe(path)
        except Exception as exc:
            return {'errors': [f'asr_node: {type(exc).__name__}: {exc}']}
        return {'transcript': tr.text, 'narrative': tr.text, 'asr_language': tr.language, 'asr_duration': tr.duration, 'asr_device': getattr(asr, 'resolved_device', ''), 'asr_flags': list(getattr(tr, 'flags', []) or [])}
    return asr_node

def make_translate_node(translator: Any):

    def translate_node(state: SliceState) -> dict:
        text = state.get('narrative') or ''
        base = {'narrative_en': text, 'translation': {}}
        provided = (state.get('provided_translation_en') or '').strip()
        if provided:
            return {'narrative_en': provided, 'translation': {'source': 'provided'}}
        if translator is None or not text.strip():
            return base
        try:
            if not translator.should_translate(text):
                return base
            if not translator.available():
                return {**base, 'errors': ['translate_node: Tamil-to-English model is unavailable; the draft uses the Tamil narrative']}
            tr = translator.translate(text)
        except Exception as exc:
            return {**base, 'errors': [f'translate_node: {type(exc).__name__}: {exc}']}
        if tr is None:
            return base
        return {'narrative_en': tr.target, 'translation': {'model': tr.model, 'seconds': round(tr.seconds, 2), 'tamil_share': round(tr.tamil_share, 3), 'sentences': tr.sentences}}
    return translate_node

def make_statute_node(classifier: StatuteClassifier, threshold: float | None=None):

    def statute_node(state: SliceState) -> dict:
        text = (state.get('narrative_en') or state.get('narrative') or '').strip()
        if not text:
            return {'predicted_ipc': [], 'errors': ['statute_node: empty narrative, nothing to classify']}
        try:
            sections = classifier.predict_sections(text, threshold)
            top = classifier.top_k(text, 5)
        except Exception as exc:
            return {'predicted_ipc': [], 'errors': [f'statute_node: {type(exc).__name__}: {exc}']}
        return {'predicted_ipc': sections, 'ipc_top_k': top, 'classifier_name': getattr(classifier, 'name', type(classifier).__name__)}
    return statute_node

def make_ipc_bns_node(ipc_map: IpcBnsMap):
    from fir.statute.elements import scan_all
    from fir.statute.ipc_bns_map import ReviewReason

    def ipc_bns_node(state: SliceState) -> dict:
        from fir.statute.cognizability import classify_section
        predicted = state.get('predicted_ipc') or []
        result = ipc_map.apply(predicted)
        review = [{**asdict(item), 'reason': item.reason.value} for item in result.review_queue]
        already = set(predicted) | {r['ipc_section'] for r in review}
        ctx = _schedule_context(state)
        cue_hits = []
        for hit in scan_all(state.get('narrative') or ''):
            if hit.ipc_section in already:
                continue
            row = ipc_map.lookup(hit.ipc_section)
            bns = row.normalised_bns if row and row.is_bns_section else None
            cue_hits.append({'ipc_section': hit.ipc_section, 'suggested_bns': bns, 'offence': row.offence if row else '', 'cognizable': classify_section(bns, ctx).value if bns else 'unknown', 'evidenced': hit.evidenced, 'total': hit.total, 'cues': list(hit.cues[:4]), 'reason': ReviewReason.CUES_PRESENT_NOT_PREDICTED.value})
        return {'bns_sections': result.bns_sections, 'auto_applied': [asdict(r) for r in result.auto_applied], 'review_queue': review, 'cue_hits': cue_hits}
    return ipc_bns_node

def _schedule_context(state: SliceState) -> dict:
    amounts = [sp for sp in state.get('extracted_spans') or [] if sp.get('kind') == 'amount_inr']
    ctx: dict = {}
    if len(amounts) == 1 and amounts[0].get('value') is not None:
        ctx['property_value_inr'] = amounts[0]['value']
    return ctx

def cognizability_node(state: SliceState) -> dict:
    result = route_case(state.get('bns_sections') or [], has_review_items=bool(state.get('review_queue')), context=_schedule_context(state))
    route, rationale = (result.route.value, result.rationale)
    if route != Route.FIR.value:
        raising = [h for h in state.get('cue_hits') or [] if h.get('cognizable') != 'non_cognizable']
        if raising:
            names = ', '.join((f"IPC {h['ipc_section']} ({', '.join(h['cues'][:2])})" for h in raising))
            route = Route.OFFICER_REVIEW.value
            rationale = f'original narrative evidences possibly cognizable offence(s) the classifier did not predict: {names}' + (f'; {result.rationale}' if result.rationale else '')
    return {'route': route, 'rationale': rationale, 'cognizability': {s: c.value for s, c in result.per_section.items()}}

def evidence_node(state: SliceState) -> dict:
    from fir.statute.evidence import build_evidence_graph
    graph = build_evidence_graph(
        narrative=state.get('narrative') or '',
        extracted_spans=state.get('extracted_spans') or [],
        predicted_ipc=state.get('predicted_ipc') or [],
        review_queue=state.get('review_queue') or [],
        cue_hits=state.get('cue_hits') or [],
        bns_sections=state.get('bns_sections') or [],
        route=state.get('route') or '',
    )
    return {'evidence_graph': graph, 'clarification_questions': graph.get('questions', [])}

def extract_node(state: SliceState) -> dict:
    from dataclasses import asdict as _asdict
    from fir.extract.rules import iter_spans
    text = state.get('narrative') or ''
    if not text.strip():
        return {'extracted_spans': []}
    try:
        spans = [{**_asdict(sp), 'kind': sp.kind.value} for sp in iter_spans(text)]
    except Exception as exc:
        return {'extracted_spans': [], 'errors': [f'extract_node: {type(exc).__name__}: {exc}']}
    return {'extracted_spans': spans}

def instantiate_node(state: SliceState) -> dict:
    from fir.extract.fill import fill_structured_slots
    from fir.instantiate.from_decision import record_from_decision
    from fir.instantiate.narrative import attach_narrative
    from fir.instantiate.render import render_if1
    try:
        decision = to_decision(state)
        rec = record_from_decision(decision)
        rep = fill_structured_slots(rec, state.get('narrative') or '')
        attach_narrative(rec)
        return {'fir_record': rec.model_dump(mode='json'), 'if1_text': render_if1(rec), 'fill_report': {'filled': sorted(rep.filled), 'ambiguous': sorted(rep.ambiguous), 'unplaced': [sp.value for sp in rep.unplaced]}, 'narrative_grounded': rec.narrative_is_grounded}
    except Exception as exc:
        return {'errors': [f'instantiate_node: {type(exc).__name__}: {exc}']}

def _entry(state: SliceState) -> str:
    return 'asr' if state.get('audio_path') else 'extract'

def build_slice_graph(classifier: StatuteClassifier, asr: Any=None, ipc_map: IpcBnsMap | None=None, threshold: float | None=None, translator: Any=None):
    ipc_map = ipc_map or IpcBnsMap.load()
    g = StateGraph(SliceState)
    g.add_node('asr', make_asr_node(asr))
    g.add_node('extract', extract_node)
    g.add_node('translate', make_translate_node(translator))
    g.add_node('statute_id', make_statute_node(classifier, threshold))
    g.add_node('ipc_bns', make_ipc_bns_node(ipc_map))
    g.add_node('cognizability_check', cognizability_node)
    g.add_node('evidence', evidence_node)
    g.add_node('instantiate', instantiate_node)
    g.add_conditional_edges(START, _entry, {'asr': 'asr', 'extract': 'extract'})
    g.add_edge('asr', 'extract')
    g.add_edge('extract', 'translate')
    g.add_edge('translate', 'statute_id')
    g.add_edge('statute_id', 'ipc_bns')
    g.add_edge('ipc_bns', 'cognizability_check')
    g.add_edge('cognizability_check', 'evidence')
    g.add_edge('evidence', 'instantiate')
    g.add_edge('instantiate', END)
    return g.compile()

def run_text(graph, narrative: str) -> SliceState:
    return graph.invoke({'narrative': narrative, 'errors': []})

def run_audio(graph, audio_path: str, reference: str='') -> SliceState:
    return graph.invoke({'audio_path': str(audio_path), 'reference_transcript': reference, 'errors': []})

def to_decision(state: SliceState):
    from fir.schema.statute_decision import StatuteDecision
    return StatuteDecision.from_state(dict(state))

def format_result(state: SliceState) -> str:
    lines: list[str] = []
    if state.get('transcript'):
        lines.append(f"  transcript   : {state['transcript'][:100]}")
        if state.get('asr_flags'):
            lines.append(f"  ! ASR flags  : {', '.join(state['asr_flags'])}")
    tr = state.get('translation') or {}
    if tr:
        lines.append(f"  translated   : ta->en via {tr.get('model', '?').split('/')[-1]} ({tr.get('sentences', '?')} sent, {tr.get('seconds', '?')}s)")
        lines.append(f"  narrative_en : {(state.get('narrative_en') or '')[:100]}")
    lines.append(f"  IPC predicted: {', '.join(state.get('predicted_ipc') or []) or '(none)'}")
    lines.append(f"  BNS applied  : {', '.join(state.get('bns_sections') or []) or '(none)'}")
    review = state.get('review_queue') or []
    if review:
        detail = ', '.join((f"{r['ipc_section']}({r['reason']})" for r in review))
        lines.append(f'  to review    : {detail}')
    else:
        lines.append('  to review    : (none)')
    cues = state.get('cue_hits') or []
    if cues:
        detail = ', '.join((f"{h['ipc_section']}[{'/'.join(h['cues'][:2])}]" for h in cues))
        lines.append(f'  cues present : {detail}  (original text; not predicted)')
    route = state.get('route', '?')
    marker = {'FIR': 'FIR', 'CSR': 'CSR', 'OFFICER_REVIEW': 'REVIEW'}.get(route, route)
    lines.append(f"  route        : {marker}  -- {state.get('rationale', '')}")
    fr = state.get('fill_report') or {}
    if fr:
        filled = ', '.join(fr.get('filled') or []) or '(none)'
        lines.append(f'  slots filled : {filled}')
        if fr.get('ambiguous'):
            lines.append(f"  ambiguous    : {', '.join(fr['ambiguous'])}")
    if 'narrative_grounded' in state:
        gate = 'PASS' if state['narrative_grounded'] else 'FAIL'
        lines.append(f'  faithfulness : {gate}')
    for err in state.get('errors') or []:
        lines.append(f'  ! {err}')
    return '\n'.join(lines)
__all__ = ['SliceState', 'to_decision', 'extract_node', 'instantiate_node', 'make_translate_node', 'StatuteClassifier', 'Route', 'build_slice_graph', 'run_text', 'run_audio', 'format_result']
