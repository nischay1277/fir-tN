from __future__ import annotations
import functools
import re
from dataclasses import dataclass
import numpy as np
from fir.data.ilsi import load_statute_texts, parse_ipc_section
_PUNISHMENT_BOILERPLATE = frozenset({'whoever', 'shall', 'punished', 'punishment', 'imprisonment', 'imprisoned', 'fine', 'fined', 'liable', 'extend', 'term', 'description', 'either', 'years', 'year', 'months', 'month', 'rupees', 'thousand', 'hundred', 'life', 'simple', 'rigorous', 'both', 'also', 'commits', 'committed', 'commit', 'offence', 'offences', 'section', 'sections', 'act', 'code', 'provided', 'case', 'cases', 'person', 'persons'})
_TOKEN_RE = re.compile("[a-z][a-z'-]+")

def _stem(w: str) -> str:
    if len(w) <= 4:
        return w
    for suf, repl in (('ies', 'y'), ('ing', ''), ('ed', ''), ('es', ''), ('s', '')):
        if w.endswith(suf) and len(w) - len(suf) >= 3:
            return w[:-len(suf)] + repl
    return w

def _stem_tokens(text: str) -> list[str]:
    return [_stem(t) for t in _TOKEN_RE.findall(text.lower())]

@dataclass(slots=True)
class StatuteHit:
    ipc_section: str
    label: str
    text: str
    score: float

class StatuteIndex:

    def __init__(self, texts: dict[str, str]):
        from sklearn.feature_extraction.text import TfidfVectorizer
        self.labels = list(texts)
        self.sections = [parse_ipc_section(lab) or lab for lab in self.labels]
        self.texts = [texts[lab] for lab in self.labels]
        self._by_section = {s: i for i, s in enumerate(self.sections)}
        from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS
        stop = sorted({_stem(w) for w in ENGLISH_STOP_WORDS | _PUNISHMENT_BOILERPLATE})
        self._vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, stop_words=stop, tokenizer=_stem_tokens, token_pattern=None)
        self._X = self._vec.fit_transform(self.texts)

    @classmethod
    @functools.lru_cache(maxsize=1)
    def load(cls) -> 'StatuteIndex':
        return cls(load_statute_texts())

    def __len__(self) -> int:
        return len(self.labels)

    def text_for(self, ipc_section: str) -> str | None:
        i = self._by_section.get(ipc_section.strip().upper())
        return self.texts[i] if i is not None else None

    def hit_for(self, ipc_section: str) -> StatuteHit | None:
        i = self._by_section.get(ipc_section.strip().upper())
        if i is None:
            return None
        return StatuteHit(self.sections[i], self.labels[i], self.texts[i], 1.0)

    def search(self, query: str, k: int=5) -> list[StatuteHit]:
        q = self._vec.transform([query])
        sims = (self._X @ q.T).toarray().ravel()
        order = np.argsort(-sims)[:k]
        return [StatuteHit(self.sections[i], self.labels[i], self.texts[i], float(sims[i])) for i in order if sims[i] > 0]

    def rank_of(self, query: str, ipc_section: str) -> int | None:
        q = self._vec.transform([query])
        sims = (self._X @ q.T).toarray().ravel()
        i = self._by_section.get(ipc_section.strip().upper())
        if i is None or sims[i] <= 0:
            return None
        return int((sims > sims[i]).sum()) + 1
