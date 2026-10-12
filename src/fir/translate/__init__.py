from __future__ import annotations

def default_translator():
    from fir.translate.indictrans import IndicTranslator
    return IndicTranslator()
