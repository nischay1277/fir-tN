from __future__ import annotations
from fir.config import ARTIFACT_DIR
TFIDF_ARTIFACT = ARTIFACT_DIR / 'models' / 'tfidf_statute.joblib'

def available() -> dict[str, bool]:
    return {'tfidf': TFIDF_ARTIFACT.exists(), 'rule': True}

def default_name() -> str:
    return 'tfidf'

def resolve(name: str='auto') -> str:
    if name == 'auto':
        return 'tfidf' if TFIDF_ARTIFACT.exists() else 'rule'
    if name == 'tfidf':
        return 'tfidf'
    if name == 'rule':
        return 'rule'
    raise ValueError('Classifier must be auto, tfidf or rule')

def load(name: str='auto'):
    selected = resolve(name)
    if selected == 'rule':
        from fir.statute.rule_classifier import RuleCueClassifier
        return RuleCueClassifier()
    from fir.statute.tfidf_baseline import TfidfStatuteClassifier
    return TfidfStatuteClassifier.load(TFIDF_ARTIFACT)
