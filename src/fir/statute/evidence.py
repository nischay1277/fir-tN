"""Evidence-first legal analysis helpers.

The graph is deliberately JSON-shaped so it can be returned by the API and
rendered by the officer UI without introducing a graph database dependency.
"""
from __future__ import annotations

from typing import Any

from fir.statute.elements import check_elements


def _question(justification: str, element: str) -> str:
    marker = "-- establish:"
    if marker in justification:
        return justification.split(marker, 1)[1].strip().rstrip("?") + "?"
    return f"What evidence establishes {element.lower()}?"


def build_evidence_graph(
    narrative: str,
    extracted_spans: list[dict[str, Any]] | None,
    predicted_ipc: list[str] | None,
    review_queue: list[dict[str, Any]] | None,
    cue_hits: list[dict[str, Any]] | None,
    bns_sections: list[str] | None,
    route: str = "",
) -> dict[str, Any]:
    """Create provenance links from extracted facts to statutory ingredients."""
    text = narrative or ""
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, str]] = []
    questions: list[dict[str, Any]] = []

    spans = extracted_spans or []
    for idx, span in enumerate(spans):
        node_id = f"fact:{idx}"
        nodes.append({
            "id": node_id,
            "type": "fact",
            "kind": span.get("kind", "narrative_span"),
            "text": span.get("text", ""),
            "value": span.get("value"),
            "start": span.get("start", 0),
            "end": span.get("end", 0),
            "confidence": span.get("confidence"),
        })

    sections: list[str] = []
    for value in (predicted_ipc or []):
        if value not in sections:
            sections.append(value)
    for row in review_queue or []:
        value = str(row.get("ipc_section", ""))
        if value and value not in sections:
            sections.append(value)
    for row in cue_hits or []:
        value = str(row.get("ipc_section", ""))
        if value and value not in sections:
            sections.append(value)

    satisfied_count = 0
    unclear_count = 0
    ingredient_count = 0
    for section in sections:
        section_id = f"section:{section}"
        nodes.append({"id": section_id, "type": "ipc_section", "label": f"IPC {section}", "section": section})
        for check_index, check in enumerate(check_elements(section, text)):
            ingredient_count += 1
            status = str(check.satisfied)
            if status == "yes":
                satisfied_count += 1
            else:
                unclear_count += 1
            ingredient_id = f"ingredient:{section}:{check_index}"
            nodes.append({
                "id": ingredient_id,
                "type": "ingredient",
                "section": section,
                "label": check.element,
                "status": status,
                "justification": check.justification,
            })
            edges.append({"source": ingredient_id, "target": section_id, "relation": "required_by"})
            linked = False
            for prov in check.supporting_provenance:
                start = prov.transcript_char_start
                end = prov.transcript_char_end
                provenance_linked = False
                for idx, span in enumerate(spans):
                    span_start = int(span.get("start", 0))
                    span_end = int(span.get("end", 0))
                    if span_start < end and span_end > start:
                        edges.append({"source": f"fact:{idx}", "target": ingredient_id, "relation": "supports"})
                        linked = True
                        provenance_linked = True
                if not provenance_linked:
                    fact_id = f"transcript:{section}:{check_index}:{start}"
                    nodes.append({"id": fact_id, "type": "transcript_span", "text": text[start:end], "start": start, "end": end})
                    edges.append({"source": fact_id, "target": ingredient_id, "relation": "supports"})
            if status == "unclear":
                q = {
                    "id": f"question:{section}:{check_index}",
                    "section": f"IPC {section}",
                    "ingredient": check.element,
                    "question": _question(check.justification, check.element),
                    "priority": "high" if check_index == 0 else "normal",
                    "reason": "The statutory ingredient is not stated clearly in the narrative.",
                }
                questions.append(q)
            elif not linked and check.supporting_provenance:
                edges.append({"source": ingredient_id, "target": section_id, "relation": "supported_by_transcript"})

    for section, bns in zip(sections, bns_sections or []):
        bns_id = f"bns:{bns}"
        if not any(node["id"] == bns_id for node in nodes):
            nodes.append({"id": bns_id, "type": "bns_section", "label": bns, "section": bns})
        edges.append({"source": f"section:{section}", "target": bns_id, "relation": "mapped_to"})
    if route:
        route_id = "route"
        nodes.append({"id": route_id, "type": "route", "value": route})
        for bns in bns_sections or []:
            edges.append({"source": f"bns:{bns}", "target": route_id, "relation": "routes"})

    return {
        "version": "1.0",
        "nodes": nodes,
        "edges": edges,
        "questions": questions,
        "summary": {
            "fact_count": sum(1 for node in nodes if node.get("type") in {"fact", "transcript_span"}),
            "section_count": len(sections),
            "ingredient_count": ingredient_count,
            "satisfied_count": satisfied_count,
            "unclear_count": unclear_count,
            "question_count": len(questions),
        },
    }


__all__ = ["build_evidence_graph"]
