from __future__ import annotations
import json
import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path
from fir.config import DATA_DIR, datasets
_LABEL_RE = re.compile('Section\\s+([0-9]+[A-Z]*)\\s+in\\s+The\\s+Indian\\s+Penal\\s+Code', re.I)
SPLITS = ('train', 'dev', 'test')

def parse_ipc_section(label: str) -> str | None:
    m = _LABEL_RE.search(label)
    return m.group(1).upper() if m else None

@dataclass(slots=True)
class FactInstance:
    id: str
    text: str
    ipc_labels: list[str] = field(default_factory=list)

    @property
    def ipc_sections(self) -> list[str]:
        out = [parse_ipc_section(lbl) for lbl in self.ipc_labels]
        return [s for s in out if s]

def _split_path(split: str) -> Path:
    if split not in SPLITS:
        raise ValueError(f'split must be one of {SPLITS}, got {split!r}')
    cfg = datasets()['ilsi']
    return DATA_DIR / 'ilsi' / cfg['files'][split]

def iter_ilsi(split: str, limit: int | None=None) -> Iterator[FactInstance]:
    path = _split_path(split)
    if not path.exists():
        raise FileNotFoundError(f'{path} not found. Run: bash scripts/download_ilsi.sh')
    with path.open(encoding='utf-8') as fh:
        for n, line in enumerate(fh):
            if limit is not None and n >= limit:
                break
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            text = rec['text']
            yield FactInstance(id=str(rec['id']), text=' '.join(text) if isinstance(text, list) else str(text), ipc_labels=list(rec.get('labels', [])))

def load_ilsi(split: str, limit: int | None=None) -> list[FactInstance]:
    return list(iter_ilsi(split, limit=limit))

def load_label_vocab() -> list[str]:
    for candidate in (DATA_DIR / 'mapping' / 'ilsi_ipc_labels.json', DATA_DIR / 'ilsi' / datasets()['ilsi']['files']['label_vocab']):
        if candidate.exists():
            vocab: dict[str, int] = json.loads(candidate.read_text(encoding='utf-8'))
            return [lbl for lbl, _ in sorted(vocab.items(), key=lambda kv: kv[1])]
    raise FileNotFoundError('no ILSI label vocabulary found under data/')

def load_statute_texts() -> dict[str, str]:
    path = DATA_DIR / 'ilsi' / datasets()['ilsi']['files']['statutes']
    if not path.exists():
        raise FileNotFoundError(f'{path} not found. Run: bash scripts/download_ilsi.sh')
    out: dict[str, str] = {}
    with path.open(encoding='utf-8') as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            text = rec.get('text', '')
            out[rec['id']] = ' '.join(text) if isinstance(text, list) else str(text)
    return out
