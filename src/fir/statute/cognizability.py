from __future__ import annotations
import csv
import functools
import re
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from fir.config import DATA_DIR

class Route(str, Enum):
    FIR = 'FIR'
    CSR = 'CSR'
    OFFICER_REVIEW = 'OFFICER_REVIEW'

class Cognizability(str, Enum):
    COGNIZABLE = 'cognizable'
    NON_COGNIZABLE = 'non_cognizable'
    CONDITIONAL = 'conditional'
    UNKNOWN = 'unknown'
UNSETTLED = frozenset({Cognizability.CONDITIONAL, Cognizability.UNKNOWN})
_STUB_SCHEDULE: dict[str, Cognizability] = {'100': Cognizability.COGNIZABLE, '101': Cognizability.COGNIZABLE, '103': Cognizability.COGNIZABLE, '105': Cognizability.COGNIZABLE, '106': Cognizability.COGNIZABLE, '108': Cognizability.COGNIZABLE, '109': Cognizability.COGNIZABLE, '110': Cognizability.COGNIZABLE, '115': Cognizability.NON_COGNIZABLE, '117': Cognizability.COGNIZABLE, '118': Cognizability.COGNIZABLE, '64': Cognizability.COGNIZABLE, '74': Cognizability.COGNIZABLE, '75': Cognizability.COGNIZABLE, '80': Cognizability.COGNIZABLE, '85': Cognizability.COGNIZABLE, '87': Cognizability.COGNIZABLE, '126': Cognizability.NON_COGNIZABLE, '127': Cognizability.COGNIZABLE, '137': Cognizability.COGNIZABLE, '140': Cognizability.COGNIZABLE, '303': Cognizability.COGNIZABLE, '304': Cognizability.COGNIZABLE, '305': Cognizability.COGNIZABLE, '309': Cognizability.COGNIZABLE, '310': Cognizability.COGNIZABLE, '316': Cognizability.COGNIZABLE, '318': Cognizability.COGNIZABLE, '324': Cognizability.NON_COGNIZABLE, '326': Cognizability.COGNIZABLE, '329': Cognizability.NON_COGNIZABLE, '331': Cognizability.COGNIZABLE, '332': Cognizability.COGNIZABLE, '61': Cognizability.COGNIZABLE, '189': Cognizability.COGNIZABLE, '190': Cognizability.COGNIZABLE, '191': Cognizability.COGNIZABLE, '221': Cognizability.NON_COGNIZABLE, '223': Cognizability.NON_COGNIZABLE, '238': Cognizability.COGNIZABLE, '281': Cognizability.COGNIZABLE, '296': Cognizability.NON_COGNIZABLE, '336': Cognizability.NON_COGNIZABLE, '351': Cognizability.NON_COGNIZABLE, '352': Cognizability.NON_COGNIZABLE, '356': Cognizability.NON_COGNIZABLE, '3': Cognizability.UNKNOWN, '45': Cognizability.UNKNOWN, '49': Cognizability.UNKNOWN}
_BNS_NUM_RE = re.compile('BNS\\s*([0-9]+)')
_BASE_RE = re.compile('^(\\d+)')
_CLAUSE_RE = re.compile('\\([0-9a-z]+\\)')
_SCHEDULE_PATH_PARTS = ('statutes', 'bnss_schedule1.csv')
_TRUTHY = {'y', 'yes', 'true', '1', 'cognizable', 'c'}
_FALSY = {'n', 'no', 'false', '0', 'non_cognizable', 'non-cognizable', 'nc'}
_COND_CLAUSE_RE = re.compile('^(\\w+)\\s*(<=|>=|<|>|==)\\s*(-?\\d+(?:\\.\\d+)?)$')

@dataclass(slots=True)
class Schedule:
    table: dict[str, Cognizability]
    source: str
    n_rows: int
    source_refs: dict[str, str] = field(default_factory=dict)
    notes: dict[str, str] = field(default_factory=dict)
    conditions: dict[str, str] = field(default_factory=dict)
    derived: set[str] = field(default_factory=set)

    @property
    def is_stub(self) -> bool:
        return self.source == 'stub'

    @staticmethod
    def _normalise(bns_section: str) -> str:
        return bns_section.upper().replace('BNS', '').replace(' ', '').strip()

    @classmethod
    def _expand(cls, key: str) -> list[str]:
        if ',' not in key:
            return [key]
        m = _BASE_RE.match(key)
        if not m:
            return [key]
        base = m.group(1)
        clauses = _CLAUSE_RE.findall(key)
        return [base + c for c in clauses] if clauses else [key]

    def _key_for(self, part: str) -> str | None:
        if part in self.table:
            return part
        m = _BASE_RE.match(part)
        if m and m.group(1) in self.table:
            return m.group(1)
        return None

    def lookup(self, bns_section: str, context: dict | None=None) -> Cognizability:
        parts = self._expand(self._normalise(bns_section))
        values: set[Cognizability] = set()
        for part in parts:
            key = self._key_for(part)
            if key is None:
                values.add(Cognizability.UNKNOWN)
                continue
            v = self.table[key]
            if v is Cognizability.CONDITIONAL and context and (key in self.conditions):
                resolved = _eval_condition(self.conditions[key], context)
                if resolved is not None:
                    v = resolved
            values.add(v)
        return values.pop() if len(values) == 1 else Cognizability.UNKNOWN

    def note_for(self, bns_section: str) -> str:
        notes = []
        for part in self._expand(self._normalise(bns_section)):
            key = self._key_for(part)
            if key is not None and self.notes.get(key):
                notes.append(self.notes[key])
        return ' | '.join(dict.fromkeys(notes))

def _eval_condition(cond: str, context: dict) -> Cognizability | None:
    for clause in filter(None, (c.strip() for c in cond.split(';'))):
        if '=' not in clause:
            continue
        expr, _, outcome = clause.rpartition('=')
        expr = expr.strip()
        out = _parse_cog(outcome)
        if expr == 'else':
            return out
        m = _COND_CLAUSE_RE.match(expr)
        if not m:
            return None
        fact, op, threshold = m.groups()
        val = context.get(fact)
        if val is None:
            return None
        try:
            x, t = (float(val), float(threshold))
        except (TypeError, ValueError):
            return None
        hit = {'<': x < t, '<=': x <= t, '>': x > t, '>=': x >= t, '==': x == t}[op]
        if hit:
            return out
    return None

def _parse_cog(v: str) -> Cognizability:
    t = (v or '').strip().lower()
    if t in _TRUTHY:
        return Cognizability.COGNIZABLE
    if t in _FALSY:
        return Cognizability.NON_COGNIZABLE
    if t == 'conditional':
        return Cognizability.CONDITIONAL
    return Cognizability.UNKNOWN

def _load_csv(path: Path) -> Schedule:
    table: dict[str, Cognizability] = {}
    refs: dict[str, str] = {}
    notes: dict[str, str] = {}
    conds: dict[str, str] = {}
    with path.open(encoding='utf-8', newline='') as fh:
        for row in csv.DictReader(fh):
            sec = Schedule._normalise(row.get('bns_section') or '')
            if not sec:
                continue
            table[sec] = _parse_cog(row.get('cognizable', ''))
            if row.get('source_ref'):
                refs[sec] = row['source_ref'].strip()
            if row.get('notes'):
                notes[sec] = row['notes'].strip()
            if row.get('condition'):
                conds[sec] = row['condition'].strip()
    n_rows = len(table)
    by_base: dict[str, list[str]] = defaultdict(list)
    for key in table:
        m = _BASE_RE.match(key)
        if m and m.group(1) != key:
            by_base[m.group(1)].append(key)
    derived: set[str] = set()
    for base, keys in by_base.items():
        if base in table:
            continue
        vals = {table[k] for k in keys}
        derived.add(base)
        if len(vals) == 1:
            table[base] = vals.pop()
            if any((k in notes for k in keys)):
                notes[base] = ' | '.join(dict.fromkeys((notes[k] for k in keys if k in notes)))
            if len(keys) == 1 and keys[0] in conds:
                conds[base] = conds[keys[0]]
        else:
            table[base] = Cognizability.UNKNOWN
            notes[base] = 'sub-clauses differ: ' + ', '.join((f'{k} {table[k].value}' for k in sorted(keys)))
        refs[base] = 'derived from ' + ', '.join(sorted(keys))
    return Schedule(table=table, source=str(path), n_rows=n_rows, source_refs=refs, notes=notes, conditions=conds, derived=derived)

@functools.lru_cache(maxsize=1)
def schedule() -> Schedule:
    path = DATA_DIR.joinpath(*_SCHEDULE_PATH_PARTS)
    if path.exists():
        return _load_csv(path)
    return Schedule(table=dict(_STUB_SCHEDULE), source='stub', n_rows=len(_STUB_SCHEDULE))

def schedule_source() -> str:
    s = schedule()
    if s.is_stub:
        return f'BNSS 2023 First Schedule -- STUB ({s.n_rows} common offences, hand-coded, not the official table; see cognizability.py)'
    return f'BNSS 2023 First Schedule -- {Path(s.source).name} ({s.n_rows} rows)'

@dataclass(slots=True)
class CognizabilityResult:
    route: Route
    per_section: dict[str, Cognizability] = field(default_factory=dict)
    unknown_sections: list[str] = field(default_factory=list)
    rationale: str = ''

    @property
    def cognizable_sections(self) -> list[str]:
        return [s for s, c in self.per_section.items() if c is Cognizability.COGNIZABLE]

    @property
    def conditional_sections(self) -> list[str]:
        return [s for s, c in self.per_section.items() if c is Cognizability.CONDITIONAL]

def base_section(bns_section: str) -> str | None:
    m = _BNS_NUM_RE.search(bns_section.upper())
    return m.group(1) if m else None

def classify_section(bns_section: str, context: dict | None=None) -> Cognizability:
    return schedule().lookup(bns_section, context)

def route_case(bns_sections: list[str], has_review_items: bool=False, context: dict | None=None) -> CognizabilityResult:
    sch = schedule()
    per_section = {s: sch.lookup(s, context) for s in bns_sections}
    unknown = [s for s, c in per_section.items() if c is Cognizability.UNKNOWN]
    conditional = [s for s, c in per_section.items() if c is Cognizability.CONDITIONAL]
    if any((c is Cognizability.COGNIZABLE for c in per_section.values())):
        cog = [s for s, c in per_section.items() if c is Cognizability.COGNIZABLE]
        return CognizabilityResult(route=Route.FIR, per_section=per_section, unknown_sections=unknown + conditional, rationale=f"cognizable offence(s) present: {', '.join(cog)}")
    if not bns_sections:
        return CognizabilityResult(route=Route.OFFICER_REVIEW, per_section=per_section, unknown_sections=unknown, rationale='no BNS section could be auto-applied')
    if unknown or conditional or has_review_items:
        why = []
        if conditional:
            why.append('cognizability is conditional: ' + '; '.join((f"{s} ({sch.note_for(s) or 'see Schedule'})" for s in conditional)))
        if unknown:
            why.append('unclassified section(s): ' + ', '.join((f'{s} ({sch.note_for(s)})' if sch.note_for(s) else s for s in unknown)))
        if has_review_items:
            why.append('unresolved IPC->BNS review items')
        return CognizabilityResult(route=Route.OFFICER_REVIEW, per_section=per_section, unknown_sections=unknown + conditional, rationale='; '.join(why))
    return CognizabilityResult(route=Route.CSR, per_section=per_section, unknown_sections=unknown, rationale='all identified offences are non-cognizable')
