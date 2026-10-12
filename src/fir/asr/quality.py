from __future__ import annotations
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

class TranscriptFlag(str, Enum):
    REPETITION_LOOP = 'repetition_loop'
    FOREIGN_SCRIPT = 'foreign_script'
    EMPTY = 'empty'
_ALLOWED_SCRIPT_PREFIXES = ('TAMIL', 'LATIN')

def _script_of(ch: str) -> str:
    try:
        return unicodedata.name(ch).split()[0]
    except ValueError:
        return 'UNKNOWN'

def foreign_script_ratio(text: str) -> tuple[float, Counter]:
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return (0.0, Counter())
    offenders: Counter = Counter()
    for c in alpha:
        s = _script_of(c)
        if not any((s.startswith(p) for p in _ALLOWED_SCRIPT_PREFIXES)):
            offenders[s] += 1
    return (sum(offenders.values()) / len(alpha), offenders)

def duplicated_fraction(text: str, n: int=4) -> tuple[float, int, str]:
    w = text.split()
    if len(w) < n:
        return (0.0, 0, '')
    positions = [tuple(w[i:i + n]) for i in range(len(w) - n + 1)]
    counts = Counter(positions)
    dup_positions = sum((1 for g in positions if counts[g] > 1))
    gram, top = counts.most_common(1)[0]
    return (dup_positions / len(positions), top, ' '.join(gram))

@dataclass(slots=True)
class QualityReport:
    flags: list[TranscriptFlag] = field(default_factory=list)
    foreign_ratio: float = 0.0
    foreign_count: int = 0
    foreign_scripts: dict[str, int] = field(default_factory=dict)
    duplicated_fraction: float = 0.0
    max_ngram_repeat: int = 0
    repeated_phrase: str = ''

    @property
    def ok(self) -> bool:
        return not self.flags

    def summary(self) -> str:
        if self.ok:
            return 'ok'
        parts = []
        if TranscriptFlag.REPETITION_LOOP in self.flags:
            parts.append(f'repetition: {self.duplicated_fraction * 100:.0f}% of transcript duplicated')
        if TranscriptFlag.FOREIGN_SCRIPT in self.flags:
            scripts = ', '.join((f'{k}:{v}' for k, v in self.foreign_scripts.items()))
            parts.append(f'foreign script: {self.foreign_count} chars ({scripts})')
        if TranscriptFlag.EMPTY in self.flags:
            parts.append('empty')
        return '; '.join(parts)

def assess(text: str, foreign_min_chars: int=2, duplicate_threshold: float=0.15, ngram: int=3) -> QualityReport:
    rep = QualityReport()
    if not text or not text.strip():
        rep.flags.append(TranscriptFlag.EMPTY)
        return rep
    rep.foreign_ratio, offenders = foreign_script_ratio(text)
    rep.foreign_count = sum(offenders.values())
    rep.foreign_scripts = dict(offenders.most_common())
    if rep.foreign_count >= foreign_min_chars:
        rep.flags.append(TranscriptFlag.FOREIGN_SCRIPT)
    rep.duplicated_fraction, rep.max_ngram_repeat, rep.repeated_phrase = duplicated_fraction(text, n=ngram)
    if rep.duplicated_fraction >= duplicate_threshold:
        rep.flags.append(TranscriptFlag.REPETITION_LOOP)
    return rep
