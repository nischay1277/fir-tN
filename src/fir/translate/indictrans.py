from __future__ import annotations
import time
from dataclasses import dataclass, field
from fir.config import pipeline
MODEL_ID = 'Helsinki-NLP/opus-mt-dra-en'
SRC_LANG = 'tam_Taml'
TGT_LANG = 'eng_Latn'

def backend_for(model_id: str) -> str:
    m = model_id.lower()
    if 'indictrans' in m:
        return 'indictrans'
    if 'nllb' in m:
        return 'nllb'
    return 'marian'

def tamil_share(text: str) -> float:
    alpha = [c for c in text if c.isalpha()]
    if not alpha:
        return 0.0
    return sum((1 for c in alpha if '\u0b80' <= c <= '\u0bff')) / len(alpha)

@dataclass(slots=True)
class Translation:
    source: str
    target: str
    model: str
    seconds: float
    tamil_share: float
    sentences: int = 0
    notes: list[str] = field(default_factory=list)

class IndicTranslator:

    def __init__(self, model_id: str | None=None, device: str | None=None, min_tamil_share: float | None=None, max_new_tokens: int | None=None):
        cfg = pipeline().get('translate', {})
        self.model_id = model_id or cfg.get('model', MODEL_ID)
        self.device = device or cfg.get('device', 'auto')
        self.min_tamil_share = min_tamil_share if min_tamil_share is not None else float(cfg.get('min_tamil_share', 0.3))
        self.max_new_tokens = max_new_tokens or int(cfg.get('max_new_tokens', 256))
        self._model = None
        self._tok = None
        self._proc = None
        self.resolved_device = ''

    def available(self) -> bool:
        try:
            from huggingface_hub import try_to_load_from_cache
            config = try_to_load_from_cache(self.model_id, 'config.json')
            weights = any(
                isinstance(try_to_load_from_cache(self.model_id, name), str)
                for name in ('model.safetensors', 'pytorch_model.bin')
            )
            return isinstance(config, str) and weights
        except Exception:
            return False

    @property
    def backend(self) -> str:
        return backend_for(self.model_id)

    def load(self):
        if self._model is not None:
            return self._model
        import torch
        from transformers import AutoModelForSeq2SeqLM, AutoTokenizer
        device = self.device
        if device == 'auto':
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
        remote = self.backend == 'indictrans'
        kw = {'trust_remote_code': True} if remote else {}
        if self.backend == 'nllb':
            kw['src_lang'] = SRC_LANG
        self._tok = AutoTokenizer.from_pretrained(self.model_id, local_files_only=True, **kw)
        self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_id, trust_remote_code=remote, local_files_only=True, torch_dtype=torch.float16 if device == 'cuda' else torch.float32).to(device).eval()
        if remote:
            try:
                from IndicTransToolkit.processor import IndicProcessor
            except ImportError as exc:
                raise RuntimeError('IndicTransToolkit is not installed: pip install IndicTransToolkit') from exc
            self._proc = IndicProcessor(inference=True)
        self.resolved_device = device
        return self._model

    def should_translate(self, text: str) -> bool:
        return tamil_share(text) >= self.min_tamil_share

    def translate(self, text: str, force: bool=False) -> Translation | None:
        share = tamil_share(text)
        if not force and share < self.min_tamil_share:
            return None
        import torch
        self.load()
        t0 = time.perf_counter()
        sents = [s.strip() for s in _split_sentences(text) if s.strip()]
        gen_kw: dict = {'num_beams': 4, 'max_new_tokens': self.max_new_tokens, 'num_return_sequences': 1}
        if self.backend == 'indictrans':
            batch = self._proc.preprocess_batch(sents, src_lang=SRC_LANG, tgt_lang=TGT_LANG)
        else:
            batch = sents
        if self.backend == 'nllb':
            gen_kw['forced_bos_token_id'] = self._tok.convert_tokens_to_ids(TGT_LANG)
        enc = self._tok(batch, padding='longest', truncation=True, max_length=256, return_tensors='pt').to(self.resolved_device)
        with torch.no_grad():
            out = self._model.generate(**enc, **gen_kw)
        decoded = self._tok.batch_decode(out, skip_special_tokens=True, clean_up_tokenization_spaces=True)
        english = self._proc.postprocess_batch(decoded, lang=TGT_LANG) if self.backend == 'indictrans' else decoded
        return Translation(source=text, target=' '.join(english).strip(), model=self.model_id, seconds=time.perf_counter() - t0, tamil_share=share, sentences=len(sents))
_SENT_END = ('।', '.', '?', '!', '\n')

def _split_sentences(text: str) -> list[str]:
    out, cur = ([], [])
    for ch in text:
        cur.append(ch)
        if ch in _SENT_END:
            out.append(''.join(cur))
            cur = []
    if cur:
        out.append(''.join(cur))
    return out
