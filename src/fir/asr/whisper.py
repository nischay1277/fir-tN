from __future__ import annotations
import ctypes
import gc
import glob
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from fir.asr.quality import QualityReport, TranscriptFlag, assess
from fir.config import pipeline
_CUDA_LIBS_PRELOADED = False

def preload_cuda_libs() -> list[str]:
    global _CUDA_LIBS_PRELOADED
    if _CUDA_LIBS_PRELOADED:
        return []
    loaded: list[str] = []
    try:
        import nvidia
        roots = [Path(p) for p in nvidia.__path__]
    except ImportError:
        roots = []
    patterns = (
        'cublas/lib/libcublasLt*.so*',
        'cublas/lib/libcublas.so*',
        'cudnn/lib/libcudnn*.so*',
    )
    for pattern in patterns:
        for root in roots:
            for path in sorted(glob.glob(str(root / pattern))):
                try:
                    ctypes.CDLL(path, mode=ctypes.RTLD_GLOBAL)
                    loaded.append(os.path.basename(path))
                except OSError:
                    continue
    _CUDA_LIBS_PRELOADED = True
    return loaded

@dataclass(slots=True)
class Transcript:
    text: str
    language: str = ''
    language_probability: float = 0.0
    duration: float = 0.0
    segments: list[dict] = field(default_factory=list)
    quality: 'QualityReport | None' = None
    retried: bool = False

    @property
    def flags(self) -> list[str]:
        return [f.value for f in self.quality.flags] if self.quality else []

class WhisperAsr:

    def __init__(self, model_name: str | None=None, compute_type: str | None=None, device: str | None=None, language: str | None=None, beam_size: int | None=None, vad_filter: bool | None=None, condition_on_previous_text: bool | None=None, temperature: float | list[float] | None=None, batch_size: int | None=None, repetition_penalty: float | None=None, no_repeat_ngram_size: int | None=None, initial_prompt: str | None=None, hotwords: str | None=None):
        cfg = pipeline()['asr']
        self.model_name = model_name or cfg['model']
        self.compute_type = compute_type or cfg['compute_type']
        self.device = device or cfg.get('device', 'auto')
        configured_language = language if language is not None else cfg.get('language', 'ta')
        self.language = None if configured_language in (None, 'auto') else configured_language
        self.beam_size = beam_size if beam_size is not None else cfg.get('beam_size', 5)
        self.vad_filter = vad_filter if vad_filter is not None else cfg.get('vad_filter', True)
        self.condition_on_previous_text = condition_on_previous_text if condition_on_previous_text is not None else cfg.get('condition_on_previous_text', False)
        self.temperature = temperature if temperature is not None else cfg.get('temperature', 0.0)
        self.batch_size = int(batch_size if batch_size is not None else cfg.get('batch_size', 0))
        self.repetition_penalty = float(repetition_penalty if repetition_penalty is not None else cfg.get('repetition_penalty', 1.0))
        self.no_repeat_ngram_size = int(no_repeat_ngram_size if no_repeat_ngram_size is not None else cfg.get('no_repeat_ngram_size', 0))
        self.initial_prompt = initial_prompt if initial_prompt is not None else cfg.get('initial_prompt')
        self.hotwords = hotwords if hotwords is not None else cfg.get('hotwords')
        self._model = None
        self._batched = None
        self.resolved_device: str = ''
        self.resolved_compute_type: str = ''

    def _candidate_devices(self) -> list[tuple[str, str]]:
        if self.device == 'cpu':
            return [('cpu', 'int8')]
        if self.device == 'cuda':
            return [('cuda', self.compute_type)]
        try:
            import torch
            cuda = torch.cuda.is_available()
        except Exception:
            cuda = False
        pairs = []
        if cuda:
            pairs.append(('cuda', self.compute_type))
        pairs.append(('cpu', 'int8'))
        return pairs

    def load(self):
        if self._model is not None:
            return self._model
        from faster_whisper import WhisperModel
        preloaded = preload_cuda_libs()
        if preloaded:
            print(f"==> preloaded CUDA libs: {', '.join(preloaded[:4])} ...", flush=True)
        errors: list[str] = []
        for device, compute_type in self._candidate_devices():
            try:
                print(f'==> loading {self.model_name} on {device} ({compute_type})', flush=True)
                self._model = WhisperModel(self.model_name, device=device, compute_type=compute_type)
                self.resolved_device = device
                self.resolved_compute_type = compute_type
                return self._model
            except Exception as exc:
                errors.append(f'{device}/{compute_type}: {type(exc).__name__}: {exc}')
                print(f'    failed on {device}, falling back', flush=True)
        raise RuntimeError('could not load faster-whisper on any device:\n  ' + '\n  '.join(errors))

    def _transcribe_once(self, audio_path: str | Path, task: str='transcribe', rescue: bool=False, language_hint: str | None=None) -> Transcript:
        model = self.load()
        language = language_hint or self.language
        prompt = self.initial_prompt if task == 'transcribe' else None
        hotwords = self.hotwords if task == 'transcribe' else None
        repetition_penalty = max(self.repetition_penalty, 1.15) if rescue else self.repetition_penalty
        no_repeat_ngram_size = max(self.no_repeat_ngram_size, 3) if rescue else self.no_repeat_ngram_size
        if self.batch_size > 0:
            if self._batched is None:
                from faster_whisper import BatchedInferencePipeline
                self._batched = BatchedInferencePipeline(model)
            segments, info = self._batched.transcribe(str(audio_path), language=language, task=task, beam_size=self.beam_size, batch_size=self.batch_size, vad_filter=True, temperature=self.temperature, repetition_penalty=repetition_penalty, no_repeat_ngram_size=no_repeat_ngram_size, chunk_length=15 if rescue else None, initial_prompt=prompt, hotwords=hotwords)
        else:
            segments, info = model.transcribe(str(audio_path), language=language, task=task, beam_size=self.beam_size, vad_filter=self.vad_filter, condition_on_previous_text=self.condition_on_previous_text, temperature=self.temperature, repetition_penalty=repetition_penalty, no_repeat_ngram_size=no_repeat_ngram_size, chunk_length=15 if rescue else None, initial_prompt=prompt, hotwords=hotwords)
        segs = [{'start': s.start, 'end': s.end, 'text': s.text} for s in segments]
        text = ' '.join((s['text'].strip() for s in segs)).strip()
        return Transcript(text=text, language=info.language, language_probability=float(info.language_probability), duration=float(info.duration), segments=segs, quality=assess(text), retried=rescue)

    def _release_model(self) -> None:
        self._batched = None
        self._model = None
        self.resolved_device = ''
        self.resolved_compute_type = ''
        gc.collect()

    def transcribe(self, audio_path: str | Path, task: str='transcribe', language_hint: str | None=None, force_rescue: bool=False) -> Transcript:
        try:
            result = self._transcribe_once(audio_path, task, rescue=force_rescue, language_hint=language_hint)
            if task == 'transcribe' and not force_rescue and result.quality and any(flag in result.quality.flags for flag in (TranscriptFlag.REPETITION_LOOP, TranscriptFlag.EMPTY)):
                recovered = self._transcribe_once(audio_path, task, rescue=True, language_hint=language_hint)
                if recovered.quality and recovered.quality.ok:
                    return recovered
            return result
        except Exception as cuda_error:
            if self.device != 'auto' or self.resolved_device != 'cuda':
                raise
            print(
                f'    CUDA inference failed ({type(cuda_error).__name__}: {cuda_error}); '
                'retrying on CPU',
                flush=True,
            )
            self._release_model()
            self.device = 'cpu'
            try:
                return self._transcribe_once(audio_path, task, rescue=force_rescue, language_hint=language_hint)
            except Exception as cpu_error:
                raise RuntimeError(
                    f'CUDA transcription failed: {cuda_error}; CPU fallback failed: {cpu_error}'
                ) from cpu_error

    def translate_audio(self, audio_path: str | Path, language_hint: str | None=None) -> Transcript:
        return self.transcribe(audio_path, task='translate', language_hint=language_hint)

    def transcribe_batch(self, audio_paths: list[str | Path], progress: bool=True) -> tuple[list[Transcript], float]:
        self.load()
        out: list[Transcript] = []
        t0 = time.perf_counter()
        for i, p in enumerate(audio_paths, 1):
            out.append(self.transcribe(p))
            if progress:
                print(f'    [{i}/{len(audio_paths)}] {Path(p).name}', flush=True)
        return (out, time.perf_counter() - t0)
