from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from fir.data.ilsi import FactInstance, load_label_vocab, parse_ipc_section

@dataclass(slots=True)
class LabelSpace:
    labels: list[str]

    @classmethod
    def from_vocab(cls) -> 'LabelSpace':
        return cls(labels=load_label_vocab())

    def __len__(self) -> int:
        return len(self.labels)

    @property
    def index(self) -> dict[str, int]:
        return {lbl: i for i, lbl in enumerate(self.labels)}

    @property
    def sections(self) -> list[str]:
        return [parse_ipc_section(lbl) or lbl for lbl in self.labels]

    def encode(self, instances: list[FactInstance]) -> np.ndarray:
        idx = self.index
        y = np.zeros((len(instances), len(self.labels)), dtype=np.float32)
        for i, inst in enumerate(instances):
            for lbl in inst.ipc_labels:
                j = idx.get(lbl)
                if j is not None:
                    y[i, j] = 1.0
        return y

    def decode(self, scores: np.ndarray, threshold: float) -> list[str]:
        secs = self.sections
        hits = np.flatnonzero(np.asarray(scores) >= threshold)
        hits = hits[np.argsort(-np.asarray(scores)[hits])]
        return [secs[j] for j in hits]

    def decode_labels(self, scores: np.ndarray, threshold: float) -> list[str]:
        hits = np.flatnonzero(np.asarray(scores) >= threshold)
        hits = hits[np.argsort(-np.asarray(scores)[hits])]
        return [self.labels[j] for j in hits]

    def top_k(self, scores: np.ndarray, k: int=5) -> list[tuple[str, float]]:
        scores = np.asarray(scores)
        secs = self.sections
        order = np.argsort(-scores)[:k]
        return [(secs[j], float(scores[j])) for j in order]
