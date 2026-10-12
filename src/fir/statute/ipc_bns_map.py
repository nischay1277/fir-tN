from __future__ import annotations
import csv
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from fir.config import DATA_DIR, pipeline, resolve
DEFAULT_MAP_PATH = DATA_DIR / 'mapping' / 'ipc_bns_map.csv'
SENTINEL_OMITTED = 'OMITTED'
SENTINEL_VERIFY = 'VERIFY'
OTHER_STATUTE_MARKERS = ('PC Act',)

class ReviewReason(str, Enum):
    LOW_CONFIDENCE = 'low_confidence'
    FLAGGED_NEEDS_REVIEW = 'flagged_needs_review'
    MAPPING_UNVERIFIED = 'mapping_unverified'
    OTHER_STATUTE = 'maps_to_other_statute'
    REPEALED_NO_EQUIVALENT = 'repealed_no_equivalent'
    NOT_IN_TABLE = 'not_in_mapping_table'
    CUES_PRESENT_NOT_PREDICTED = 'cues_present_not_predicted'

@dataclass(frozen=True, slots=True)
class MapRow:
    ipc_section: str
    offence: str
    bns_section: str
    confidence: str
    needs_review: bool
    notes: str = ''

    @property
    def is_bns_section(self) -> bool:
        v = self.bns_section.strip()
        if not v or v in (SENTINEL_OMITTED, SENTINEL_VERIFY):
            return False
        return not any((m in v for m in OTHER_STATUTE_MARKERS))

    @property
    def normalised_bns(self) -> str:
        v = self.bns_section.strip()
        return v if v.upper().startswith('BNS ') else 'BNS ' + v

@dataclass(frozen=True, slots=True)
class ReviewItem:
    ipc_section: str
    reason: ReviewReason
    offence: str = ''
    suggested_bns: str | None = None
    confidence: str | None = None
    notes: str = ''

@dataclass(slots=True)
class MappingResult:
    bns_sections: list[str] = field(default_factory=list)
    auto_applied: list[MapRow] = field(default_factory=list)
    review_queue: list[ReviewItem] = field(default_factory=list)

    @property
    def n_auto(self) -> int:
        return len(self.auto_applied)

    @property
    def n_review(self) -> int:
        return len(self.review_queue)

    def summary(self) -> str:
        auto = ', '.join(self.bns_sections) or 'none'
        return f'{self.n_auto} auto-applied ({auto}); {self.n_review} to review'

class IpcBnsMap:

    def __init__(self, rows: dict[str, MapRow], auto_apply_confidence: set[str]):
        self._rows = rows
        self._auto_conf = auto_apply_confidence

    @classmethod
    def load(cls, path: str | Path | None=None) -> 'IpcBnsMap':
        cfg = pipeline().get('ipc_bns', {})
        path = resolve(path or cfg.get('map_path', DEFAULT_MAP_PATH))
        if not Path(path).exists():
            raise FileNotFoundError(f'IPC->BNS map not found: {path}')
        rows: dict[str, MapRow] = {}
        with open(path, encoding='utf-8', newline='') as fh:
            for r in csv.DictReader(fh):
                sec = r['ipc_section'].strip().upper()
                rows[sec] = MapRow(ipc_section=sec, offence=r.get('offence', '').strip(), bns_section=r.get('bns_section', '').strip(), confidence=r.get('confidence', '').strip().lower(), needs_review=r.get('needs_review', '').strip().upper() == 'Y', notes=r.get('notes', '').strip())
        conf = set(cfg.get('auto_apply_confidence', ['high']))
        return cls(rows, conf)

    def __len__(self) -> int:
        return len(self._rows)

    def __contains__(self, ipc_section: str) -> bool:
        return ipc_section.strip().upper() in self._rows

    def lookup(self, ipc_section: str) -> MapRow | None:
        return self._rows.get(ipc_section.strip().upper())

    def auto_applicable(self, row: MapRow) -> bool:
        return row.confidence in self._auto_conf and (not row.needs_review) and row.is_bns_section

    def apply(self, ipc_sections: list[str]) -> MappingResult:
        result = MappingResult()
        seen: set[str] = set()
        for raw in ipc_sections:
            sec = raw.strip().upper()
            if not sec or sec in seen:
                continue
            seen.add(sec)
            row = self.lookup(sec)
            if row is None:
                result.review_queue.append(ReviewItem(ipc_section=sec, reason=ReviewReason.NOT_IN_TABLE))
                continue
            if self.auto_applicable(row):
                result.auto_applied.append(row)
                bns = row.normalised_bns
                if bns not in result.bns_sections:
                    result.bns_sections.append(bns)
            else:
                result.review_queue.append(ReviewItem(ipc_section=sec, reason=_review_reason(row, self._auto_conf), offence=row.offence, suggested_bns=row.bns_section or None, confidence=row.confidence, notes=row.notes))
        return result

    def coverage(self) -> dict[str, int]:
        auto = sum((1 for r in self._rows.values() if self.auto_applicable(r)))
        return {'total': len(self._rows), 'auto_applicable': auto, 'needs_review': sum((1 for r in self._rows.values() if r.needs_review)), 'non_bns_targets': sum((1 for r in self._rows.values() if not r.is_bns_section))}

def _review_reason(row: MapRow, auto_conf: set[str]) -> ReviewReason:
    v = row.bns_section.strip()
    if v == SENTINEL_OMITTED:
        return ReviewReason.REPEALED_NO_EQUIVALENT
    if v == SENTINEL_VERIFY or not v:
        return ReviewReason.MAPPING_UNVERIFIED
    if any((m in v for m in OTHER_STATUTE_MARKERS)):
        return ReviewReason.OTHER_STATUTE
    if row.needs_review:
        return ReviewReason.FLAGGED_NEEDS_REVIEW
    if row.confidence not in auto_conf:
        return ReviewReason.LOW_CONFIDENCE
    return ReviewReason.FLAGGED_NEEDS_REVIEW
