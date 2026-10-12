from __future__ import annotations
import re
from dataclasses import dataclass
from enum import Enum

class Kind(str, Enum):
    UNIT = 'unit'
    TENS = 'tens'
    HUNDREDS = 'hundreds'
    MULT = 'mult'

@dataclass(slots=True)
class NumberSpan:
    text: str
    start: int
    end: int
    value: int
    ordinal: bool = False
    lang: str = 'ta'
_TA: dict[str, tuple[int, Kind]] = {}

def _add(value: int, kind: Kind, *forms: str) -> None:
    for f in forms:
        _TA[f] = (value, kind)
_add(1, Kind.UNIT, 'ஒன்று', 'ஒன்னு', 'ஒரு', 'ஓர்', 'ஓர', 'ஒன்ற')
_add(2, Kind.UNIT, 'இரண்டு', 'ரெண்டு', 'இரண்ட', 'ரெண்ட', 'இரு')
_add(3, Kind.UNIT, 'மூன்று', 'மூணு', 'மூன்ற')
_add(4, Kind.UNIT, 'நான்கு', 'நாலு', 'நான்க', 'நால')
_add(5, Kind.UNIT, 'ஐந்து', 'அஞ்சு', 'ஐந்த', 'அஞ்ச')
_add(6, Kind.UNIT, 'ஆறு', 'ஆற', 'அறு')
_add(7, Kind.UNIT, 'ஏழு', 'ஏழ', 'எழு')
_add(8, Kind.UNIT, 'எட்டு', 'எட்ட', 'எண்')
_add(9, Kind.UNIT, 'ஒன்பது', 'ஒம்பது', 'ஒன்பத', 'ஒம்பத')
_add(10, Kind.TENS, 'பத்து', 'பத்த')
_add(11, Kind.UNIT, 'பதினொன்று', 'பதினொன்னு', 'பதினொன்ற')
_add(12, Kind.UNIT, 'பன்னிரண்டு', 'பன்னிரெண்டு', 'பன்னிரண்ட')
_add(13, Kind.UNIT, 'பதிமூன்று', 'பதிமூணு', 'பதிமூன்ற')
_add(14, Kind.UNIT, 'பதினான்கு', 'பதினாலு', 'பதினான்க')
_add(15, Kind.UNIT, 'பதினைந்து', 'பதினஞ்சு', 'பதினைந்த')
_add(16, Kind.UNIT, 'பதினாறு', 'பதினாற')
_add(17, Kind.UNIT, 'பதினேழு', 'பதினேழ')
_add(18, Kind.UNIT, 'பதினெட்டு', 'பதினெட்ட')
_add(19, Kind.UNIT, 'பத்தொன்பது', 'பத்தொம்பது', 'பத்தொன்பத')
_add(20, Kind.TENS, 'இருபது', 'இருபத்', 'இருபத', 'இருவது')
_add(30, Kind.TENS, 'முப்பது', 'முப்பத்', 'முப்பத')
_add(40, Kind.TENS, 'நாற்பது', 'நாற்பத்', 'நாற்பத', 'நாப்பது', 'நாப்பத்', 'நாப்பத')
_add(50, Kind.TENS, 'ஐம்பது', 'ஐம்பத்', 'ஐம்பத', 'அம்பது', 'அம்பத்', 'அம்பத')
_add(60, Kind.TENS, 'அறுபது', 'அறுபத்', 'அறுபத', 'அறுவது')
_add(70, Kind.TENS, 'எழுபது', 'எழுபத்', 'எழுபத', 'எழுவது')
_add(80, Kind.TENS, 'எண்பது', 'எண்பத்', 'எண்பத')
_add(90, Kind.TENS, 'தொண்ணூறு', 'தொண்ணூற்ற', 'தொண்ணூற்று', 'தொண்ணூத்')
_add(100, Kind.HUNDREDS, 'நூறு', 'நூற்று', 'நூற்ற')
_add(200, Kind.HUNDREDS, 'இருநூறு', 'இருநூற்று', 'இருநூற்ற')
_add(300, Kind.HUNDREDS, 'முன்னூறு', 'முந்நூறு', 'முன்னூற்று', 'முன்னூற்ற')
_add(400, Kind.HUNDREDS, 'நானூறு', 'நானூற்று', 'நானூற்ற')
_add(500, Kind.HUNDREDS, 'ஐநூறு', 'ஐந்நூறு', 'ஐநூற்று', 'ஐநூற்ற', 'அஞ்சூறு')
_add(600, Kind.HUNDREDS, 'அறுநூறு', 'அறுநூற்று', 'அறுநூற்ற')
_add(700, Kind.HUNDREDS, 'எழுநூறு', 'எழுநூற்று', 'எழுநூற்ற')
_add(800, Kind.HUNDREDS, 'எண்ணூறு', 'எண்ணூற்று', 'எண்ணூற்ற')
_add(900, Kind.HUNDREDS, 'தொள்ளாயிரம்', 'தொள்ளாயிரத்')
_add(1000, Kind.MULT, 'ஆயிரம்', 'ஆயிரத்', 'ஆயிர')
_add(100000, Kind.MULT, 'லட்சம்', 'லட்சத்', 'லச்சம்', 'லச்சத்', 'இலட்சம்')
_add(10000000, Kind.MULT, 'கோடி', 'கோடிய')
_VOWEL_SIGN = {'ஆ': 'ா', 'இ': 'ி', 'ஈ': 'ீ', 'உ': 'ு', 'ஊ': 'ூ', 'எ': 'ெ', 'ஏ': 'ே', 'ஐ': 'ை', 'ஒ': 'ொ', 'ஓ': 'ோ', 'அ': ''}
for _form, _entry in list(_TA.items()):
    if _form and _form[0] in _VOWEL_SIGN:
        _joined = _VOWEL_SIGN[_form[0]] + _form[1:]
        if _joined and _joined not in _TA:
            _TA[_joined] = _entry
_ORDINAL_TA = ('ஆவது', 'ாவது', 'ஆம்', 'ாம்', 'வது')
_GLUE_TA = ('த்', 'த', 'ு', '்')
_TA_KEYS = sorted(_TA, key=len, reverse=True)
_EN: dict[str, tuple[int, Kind]] = {}
for i, w in enumerate(['zero', 'one', 'two', 'three', 'four', 'five', 'six', 'seven', 'eight', 'nine', 'ten', 'eleven', 'twelve', 'thirteen', 'fourteen', 'fifteen', 'sixteen', 'seventeen', 'eighteen', 'nineteen']):
    _EN[w] = (i, Kind.TENS if i == 10 else Kind.UNIT)
for w, v in [('twenty', 20), ('thirty', 30), ('forty', 40), ('fifty', 50), ('sixty', 60), ('seventy', 70), ('eighty', 80), ('ninety', 90)]:
    _EN[w] = (v, Kind.TENS)
_EN['hundred'] = (100, Kind.HUNDREDS)
for w, v in [('thousand', 1000), ('lakh', 100000), ('lakhs', 100000), ('lac', 100000), ('lacs', 100000), ('crore', 10000000), ('crores', 10000000), ('million', 1000000)]:
    _EN[w] = (v, Kind.MULT)
_EN_ORDINAL = {'first': 1, 'second': 2, 'third': 3, 'fifth': 5, 'eighth': 8, 'ninth': 9, 'twelfth': 12, 'twentieth': 20, 'thirtieth': 30}

def _en_ordinal(w: str) -> int | None:
    if w in _EN_ORDINAL:
        return _EN_ORDINAL[w]
    if w.endswith('th'):
        stem = w[:-2]
        if stem in _EN and _EN[stem][1] is not Kind.MULT:
            return _EN[stem][0]
    if w.endswith('ieth'):
        stem = w[:-4] + 'y'
        if stem in _EN:
            return _EN[stem][0]
    return None
_TA_DIGITS = str.maketrans('௦௧௨௩௪௫௬௭௮௯', '0123456789')

def _accumulate(tokens: list[tuple[int, Kind]]) -> int | None:
    total = 0
    current = 0
    last_mult = None
    saw_hundred = False
    for value, kind in tokens:
        if kind is Kind.MULT:
            if last_mult is not None and value >= last_mult:
                return None
            total += (current or 1) * value
            current = 0
            saw_hundred = False
            last_mult = value
        elif kind is Kind.HUNDREDS:
            if saw_hundred:
                return None
            current = current * 100 if value == 100 and current else current + value
            saw_hundred = True
        elif kind is Kind.TENS:
            if current % 100 >= 10:
                return None
            current += value
        else:
            if 0 < current % 10 or (current % 100 >= 11 and current % 100 <= 19):
                return None
            current += value
    return total + current

def _lex_ta(word: str) -> tuple[list[tuple[int, Kind]], bool] | None:
    ordinal = False
    for suf in _ORDINAL_TA:
        if word.endswith(suf) and len(word) > len(suf):
            word = word[:-len(suf)]
            ordinal = True
            break
    tokens: list[tuple[int, Kind]] = []
    i = 0
    n = len(word)
    while i < n:
        matched = False
        for key in _TA_KEYS:
            if word.startswith(key, i):
                tokens.append(_TA[key])
                i += len(key)
                matched = True
                break
        if matched:
            continue
        glued = False
        if tokens:
            for g in _GLUE_TA:
                if word.startswith(g, i):
                    i += len(g)
                    glued = True
                    break
        if not glued:
            return None
    return (tokens, ordinal) if tokens else None
_WORD_RE = re.compile('[\u0b80-\u0bffA-Za-z]+')

def number_spans(text: str) -> list[NumberSpan]:
    text_t = text.translate(_TA_DIGITS)
    spans: list[NumberSpan] = []
    words: list[tuple[int, int, list[tuple[int, Kind]], bool, str]] = []
    for m in _WORD_RE.finditer(text_t):
        w = m.group(0)
        low = w.lower()
        if low in _EN:
            words.append((m.start(), m.end(), [_EN[low]], False, 'en'))
        elif _en_ordinal(low) is not None:
            v = _en_ordinal(low)
            words.append((m.start(), m.end(), [(v, Kind.TENS if v % 10 == 0 else Kind.UNIT)], True, 'en'))
        elif low in ('and',):
            words.append((m.start(), m.end(), [], False, 'glue'))
        else:
            lexed = _lex_ta(w)
            if lexed:
                words.append((m.start(), m.end(), lexed[0], lexed[1], 'ta'))
            else:
                words.append((m.start(), m.end(), [], False, 'other'))
    i = 0
    while i < len(words):
        s, e, toks, ordn, lang = words[i]
        if not toks:
            i += 1
            continue
        run_tokens = list(toks)
        run_end = e
        run_ord = ordn
        run_lang = lang
        j = i + 1
        while j < len(words):
            s2, e2, toks2, ordn2, lang2 = words[j]
            if lang2 == 'glue':
                j += 1
                continue
            if not toks2 or lang2 != run_lang:
                break
            trial = run_tokens + toks2
            if _accumulate(trial) is None:
                break
            run_tokens = trial
            run_end = e2
            run_ord = ordn2
            j += 1
        value = _accumulate(run_tokens)
        only_mult = all((k is Kind.MULT for _, k in run_tokens))
        prev = text_t[:s].rstrip()
        if only_mult and prev and prev[-1].isdigit():
            value = None
        if value is not None:
            spans.append(NumberSpan(text[s:run_end], s, run_end, value, run_ord, run_lang))
        i = j if j > i + 1 else i + 1
    return spans

@dataclass(slots=True)
class NormalisedText:
    text: str
    _start: list[int]
    _end: list[int]
    spans: list[NumberSpan]
    original: str = ''

    def to_original(self, a: int, b: int) -> tuple[int, int]:
        if a >= b:
            return (self._start[a] if a < len(self._start) else len(self._start),) * 2
        return (self._start[a], self._end[b - 1])

def normalise_numbers_mapped(text: str) -> NormalisedText:
    spans = number_spans(text)
    out: list[str] = []
    starts: list[int] = []
    ends: list[int] = []
    last = 0
    for sp in spans:
        for i in range(last, sp.start):
            out.append(text[i])
            starts.append(i)
            ends.append(i + 1)
        digits = str(sp.value) + ('th' if sp.ordinal and sp.lang == 'en' else '')
        for _ in digits:
            starts.append(sp.start)
            ends.append(sp.end)
        out.append(digits)
        last = sp.end
    for i in range(last, len(text)):
        out.append(text[i])
        starts.append(i)
        ends.append(i + 1)
    return NormalisedText(''.join(out), starts, ends, spans, text)

def normalise_numbers(text: str) -> str:
    return normalise_numbers_mapped(text).text
