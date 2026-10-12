from __future__ import annotations

from fir.statute.elements import scan_all


class RuleCueClassifier:
    name = 'rule-cue'

    def predict_sections(self, text: str, threshold: float | None = None) -> list[str]:
        minimum = 1.0 if threshold is None else max(0.5, min(1.0, threshold))
        return [hit.ipc_section for hit in scan_all(text, min_fraction=minimum)]

    def top_k(self, text: str, k: int = 5) -> list[tuple[str, float]]:
        hits = scan_all(text, min_fraction=0.01)
        return [(hit.ipc_section, hit.fraction) for hit in hits[:k]]
