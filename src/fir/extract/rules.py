from __future__ import annotations
import re
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Iterator
from fir.schema.if1 import ExtractedField, Provenance

class Kind(str, Enum):
    DATE = 'date'
    TIME = 'time'
    AMOUNT_INR = 'amount_inr'
    PHONE = 'phone'
    VEHICLE = 'vehicle'

@dataclass(slots=True)
class Span:
    kind: Kind
    text: str
    start: int
    end: int
    value: str | float | int | None
    confidence: float
    alternatives: list[str] = field(default_factory=list)

    def provenance(self, utterance_id: str | None=None) -> Provenance:
        return Provenance(utterance_id=utterance_id, transcript_char_start=self.start, transcript_char_end=self.end)

    def to_field(self, utterance_id: str | None=None) -> ExtractedField:
        note = None
        if self.alternatives:
            note = 'ambiguous; alternatives: ' + ', '.join(self.alternatives)
        f = ExtractedField.extracted(self.value, ta=self.text if _has_tamil(self.text) else None, en=self.text if not _has_tamil(self.text) else None, confidence=self.confidence, provenance=[self.provenance(utterance_id)])
        f.officer_note = note
        return f

def _has_tamil(s: str) -> bool:
    return any(('\u0b80' <= c <= '\u0bff' for c in s))

def _normalised(text: str):
    from fir.asr.itn import normalise_numbers_mapped
    return normalise_numbers_mapped(text)

def _span(norm, kind: Kind, a: int, b: int, value, conf: float, alts=None) -> Span:
    oa, ob = norm.to_original(a, b)
    return Span(kind, norm.original[oa:ob].strip(), oa, ob, value, conf, alts or [])

def _overlaps_spoken(norm, a: int, b: int, ordinal_only: bool=False) -> bool:
    oa, ob = norm.to_original(a, b)
    return any((sp.start < ob and oa < sp.end and (sp.ordinal or not ordinal_only) for sp in norm.spans))
_MONTHS_EN = {m: i for i, m in enumerate(['january', 'february', 'march', 'april', 'may', 'june', 'july', 'august', 'september', 'october', 'november', 'december'], 1)}
_MONTHS_EN.update({m[:3]: i for m, i in list(_MONTHS_EN.items())})
_MONTHS_EN['sept'] = 9
_MONTHS_TA = {'ஜனவரி': 1, 'பிப்ரவரி': 2, 'மார்ச்': 3, 'ஏப்ரல்': 4, 'மே': 5, 'ஜூன்': 6, 'ஜூலை': 7, 'ஆகஸ்ட்': 8, 'செப்டம்பர்': 9, 'அக்டோபர்': 10, 'நவம்பர்': 11, 'டிசம்பர்': 12}
_MONTH_ALT = '|'.join(sorted(map(re.escape, list(_MONTHS_EN) + list(_MONTHS_TA)), key=len, reverse=True))
_NUMERIC_DATE = re.compile('(?<!\\d)(\\d{1,2})[./-](\\d{1,2})[./-](\\d{4}|\\d{2})(?!\\d)')
_WORD_DATE = re.compile(f'(?<!\\d)(?:(\\d{{1,2}})(?:st|nd|rd|th)?\\s*(?:of\\s+)?({_MONTH_ALT})\\s*,?\\s*(\\d{{4}})|({_MONTH_ALT})\\s+(\\d{{1,2}})(?:st|nd|rd|th)?\\s*,?\\s*(\\d{{4}})|(\\d{{4}})\\s+({_MONTH_ALT})\\s+(\\d{{1,2}}))(?!\\d)', re.IGNORECASE)

def _month_num(name: str) -> int | None:
    n = name.lower()
    return _MONTHS_EN.get(n) or _MONTHS_TA.get(name)

def _valid(y: int, m: int, d: int) -> bool:
    try:
        date(y, m, d)
        return True
    except ValueError:
        return False

def _year4(y: str) -> int:
    v = int(y)
    return v if v >= 100 else 2000 + v if v < 50 else 1900 + v
_YEARLESS_DATE = re.compile(f'(?<!\\d)(?:({_MONTH_ALT})\\s+(?:மாதம்\\s+)?(\\d{{1,2}})(?:st|nd|rd|th)?\\s*(?:ஆம்\\s*)?(?:தேதி)?|(\\d{{1,2}})(?:st|nd|rd|th)?\\s*(?:ஆம்\\s*)?(?:தேதி\\s+)?(?:of\\s+)?({_MONTH_ALT}))(?!\\s*,?\\s*\\d{{4}})(?![\\d\\w])', re.IGNORECASE)

def extract_dates(text: str) -> list[Span]:
    norm = _normalised(text)
    t = norm.text
    out: list[Span] = []
    for m in _NUMERIC_DATE.finditer(t):
        a, b, y = (int(m.group(1)), int(m.group(2)), _year4(m.group(3)))
        dmy = _valid(y, b, a)
        mdy = _valid(y, a, b)
        if not dmy and (not mdy):
            continue
        if dmy:
            value = date(y, b, a).isoformat()
            alts = [date(y, a, b).isoformat()] if mdy and a != b else []
            conf = 0.9 if not alts else 0.7
        else:
            value = date(y, a, b).isoformat()
            alts, conf = ([], 0.6)
        out.append(_span(norm, Kind.DATE, m.start(), m.end(), value, conf, alts))
    for m in _WORD_DATE.finditer(t):
        if m.group(1):
            d, mon, y = (int(m.group(1)), _month_num(m.group(2)), int(m.group(3)))
        elif m.group(4):
            mon, d, y = (_month_num(m.group(4)), int(m.group(5)), int(m.group(6)))
        else:
            y, mon, d = (int(m.group(7)), _month_num(m.group(8)), int(m.group(9)))
        if mon and _valid(y, mon, d):
            out.append(_span(norm, Kind.DATE, m.start(), m.end(), date(y, mon, d).isoformat(), 0.95))
    covered = [(sp.start, sp.end) for sp in out]
    for m in _YEARLESS_DATE.finditer(t):
        if m.group(1):
            mon, d = (_month_num(m.group(1)), int(m.group(2)))
        else:
            d, mon = (int(m.group(3)), _month_num(m.group(4)))
        if not mon or not _valid(2000, mon, d):
            continue
        oa, ob = norm.to_original(m.start(), m.end())
        if any((a < ob and oa < b for a, b in covered)):
            continue
        out.append(_span(norm, Kind.DATE, m.start(), m.end(), f'--{mon:02d}-{d:02d}', 0.6, ['year not stated']))
    return _dedupe(out)
_TOD_TA = {'காலை': 'am', 'மதியம்': 'pm', 'மாலை': 'pm', 'இரவு': 'pm', 'அதிகாலை': 'am'}
_TOD_EN = {'morning': 'am', 'afternoon': 'pm', 'evening': 'pm', 'night': 'pm', 'noon': 'pm'}
_TOD_ALT = '|'.join(sorted(map(re.escape, list(_TOD_TA) + list(_TOD_EN)), key=len, reverse=True))
_TIME = re.compile(f"(?:({_TOD_ALT})\\s+)?(?<!\\d)(\\d{{1,2}})(?:[:.](\\d{{2}}))?(?:\\s*(a\\.?m\\.?|p\\.?m\\.?|o'?clock|மணிக்கு|மணி(?:யளவில்)?))?(?:\\s+(?:in\\s+the\\s+)?({_TOD_ALT}))?", re.IGNORECASE)

def extract_times(text: str) -> list[Span]:
    norm = _normalised(text)
    out: list[Span] = []
    for m in _TIME.finditer(norm.text):
        tod_before, hh, mm, marker, tod_after = m.groups()
        if not (marker or tod_before or tod_after):
            continue
        h = int(hh)
        if h > 24 or (mm and int(mm) > 59):
            continue
        tod = tod_before or tod_after or ''
        half = _TOD_TA.get(tod) or _TOD_EN.get(tod.lower()) or None
        mk = (marker or '').lower().replace('.', '')
        if mk.startswith('p'):
            half = 'pm'
        elif mk.startswith('a'):
            half = 'am'
        if half == 'pm' and 1 <= h < 12:
            h += 12
        if half == 'am' and h == 12:
            h = 0
        conf = 0.9 if mm or marker else 0.75
        if half is None and h <= 12:
            conf -= 0.15
        out.append(_span(norm, Kind.TIME, m.start(), m.end(), f'{h:02d}:{int(mm or 0):02d}', round(conf, 2)))
    return _dedupe(out)
_SCALE = {'lakh': 100000.0, 'lakhs': 100000.0, 'lac': 100000.0, 'lacs': 100000.0, 'லட்சம்': 100000.0, 'crore': 10000000.0, 'crores': 10000000.0, 'கோடி': 10000000.0, 'thousand': 1000.0, 'ஆயிரம்': 1000.0, 'k': 1000.0}
_SCALE_ALT = '|'.join(sorted(map(re.escape, _SCALE), key=len, reverse=True))
_CUR = '(?:₹|rs\\.?|inr|rupees?|ரூபாய்|ரூ\\.?)'
_NUM = '(\\d{1,3}(?:,\\d{2,3})+|\\d+)(?:\\.(\\d{1,2}))?'
_AMOUNT = re.compile(f'(?:{_CUR}\\s*{_NUM}\\s*({_SCALE_ALT})?|{_NUM}\\s*({_SCALE_ALT})?\\s*{_CUR})', re.IGNORECASE)

def extract_amounts_inr(text: str) -> list[Span]:
    norm = _normalised(text)
    out: list[Span] = []
    for m in _AMOUNT.finditer(norm.text):
        g = m.groups()
        whole, frac, scale = (g[0], g[1], g[2]) if g[0] else (g[3], g[4], g[5])
        if not whole:
            continue
        if _overlaps_spoken(norm, m.start(), m.end(), ordinal_only=True):
            continue
        n = float(whole.replace(',', '') + (f'.{frac}' if frac else ''))
        if scale:
            n *= _SCALE[scale.lower()] if scale.lower() in _SCALE else _SCALE[scale]
        conf = 0.85 if _overlaps_spoken(norm, m.start(), m.end()) else 0.9
        out.append(_span(norm, Kind.AMOUNT_INR, m.start(), m.end(), round(n, 2), conf))
    return _dedupe(out)
_PHONE = re.compile('(?<!\\d)(?:\\+?91[\\s-]?|0)?([6-9]\\d{4}[\\s-]?\\d{5})(?!\\d)')
_VEHICLE = re.compile('\\b([A-Z]{2})[\\s-]?(\\d{1,2})[\\s-]?([A-Z]{1,3})[\\s-]?(\\d{4})\\b')

def extract_phone_numbers(text: str) -> list[Span]:
    out = []
    for m in _PHONE.finditer(text):
        digits = re.sub('\\D', '', m.group(1))
        out.append(Span(Kind.PHONE, m.group(0).strip(), m.start(), m.end(), digits, 0.9))
    return _dedupe(out)

def extract_vehicle_numbers(text: str) -> list[Span]:
    out = []
    for m in _VEHICLE.finditer(text):
        norm = f'{m.group(1)} {int(m.group(2)):02d} {m.group(3)} {m.group(4)}'
        out.append(Span(Kind.VEHICLE, m.group(0), m.start(), m.end(), norm, 0.85))
    return _dedupe(out)

def _dedupe(spans: list[Span]) -> list[Span]:
    spans = sorted(spans, key=lambda s: (s.start, -(s.end - s.start)))
    out: list[Span] = []
    for s in spans:
        if out and out[-1].kind == s.kind and (s.start >= out[-1].start) and (s.end <= out[-1].end):
            continue
        out.append(s)
    return out

def extract_all(text: str) -> dict[Kind, list[Span]]:
    return {Kind.DATE: extract_dates(text), Kind.TIME: extract_times(text), Kind.AMOUNT_INR: extract_amounts_inr(text), Kind.PHONE: extract_phone_numbers(text), Kind.VEHICLE: extract_vehicle_numbers(text)}

def iter_spans(text: str) -> Iterator[Span]:
    for spans in extract_all(text).values():
        yield from spans
