from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import threading
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile

_LOCK = threading.RLock()
_ID = re.compile(r'[0-9a-f]{32}\Z')
_MIME = {
    '.wav': 'audio/wav',
    '.mp3': 'audio/mpeg',
    '.m4a': 'audio/mp4',
    '.mp4': 'audio/mp4',
    '.webm': 'audio/webm',
    '.ogg': 'audio/ogg',
    '.opus': 'audio/ogg',
    '.flac': 'audio/flac',
}


def storage_dir() -> Path:
    override = os.environ.get('FIR_RECORDINGS_DIR')
    if override:
        return Path(override).expanduser().absolute()
    base = Path(os.environ.get('XDG_DATA_HOME') or Path.home() / '.local' / 'share')
    return base / 'tn-fir-speech' / 'recordings'


def _ensure_dir() -> Path:
    root = storage_dir()
    root.mkdir(parents=True, mode=0o700, exist_ok=True)
    if root.is_symlink() or not root.is_dir() or stat.S_IMODE(root.stat().st_mode) & 0o077:
        raise RuntimeError(f'Recordings directory must be a private directory (0700): {root}')
    return root


def _metadata_path(recording_id: str) -> Path:
    if not _ID.fullmatch(recording_id):
        raise HTTPException(status_code=404, detail='Recording not found')
    return storage_dir() / f'{recording_id}.json'


def _write_metadata(metadata: dict) -> None:
    root = _ensure_dir()
    target = root / f"{metadata['id']}.json"
    temporary = root / f"{metadata['id']}.{uuid4().hex}.tmp"
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as handle:
            json.dump(metadata, handle, ensure_ascii=False, sort_keys=True)
            handle.write('\n')
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def store_upload(file: UploadFile, suffix: str, max_bytes: int) -> dict:
    root = _ensure_dir()
    recording_id = uuid4().hex
    path = root / f'{recording_id}{suffix}'
    digest = hashlib.sha256()
    size = 0
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0), 0o600)
    try:
        with os.fdopen(fd, 'wb') as handle:
            while chunk := file.file.read(1024 * 1024):
                size += len(chunk)
                if size > max_bytes:
                    raise HTTPException(status_code=413, detail='Audio exceeds 25 MB')
                digest.update(chunk)
                handle.write(chunk)
            if not size:
                raise HTTPException(status_code=400, detail='Audio file is empty')
            handle.flush()
            os.fsync(handle.fileno())
        metadata = {
            'id': recording_id,
            'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'original_filename': Path(file.filename or 'recording').name[:255],
            'content_type': _MIME[suffix],
            'suffix': suffix,
            'size_bytes': size,
            'sha256': digest.hexdigest(),
            'status': 'processing',
            'drafts': [],
        }
        with _LOCK:
            _write_metadata(metadata)
        return metadata
    except Exception:
        path.unlink(missing_ok=True)
        raise


def get(recording_id: str) -> dict:
    path = _metadata_path(recording_id)
    try:
        with path.open(encoding='utf-8') as handle:
            metadata = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=404, detail='Recording not found') from exc
    if metadata.get('id') != recording_id or metadata.get('suffix') not in _MIME:
        raise HTTPException(status_code=404, detail='Recording not found')
    return metadata


def audio_path(recording_id: str) -> Path:
    metadata = get(recording_id)
    path = storage_dir() / f"{recording_id}{metadata['suffix']}"
    if not path.is_file() or path.is_symlink():
        raise HTTPException(status_code=404, detail='Recording not found')
    return path


def update(recording_id: str, **values) -> dict:
    with _LOCK:
        metadata = get(recording_id)
        metadata.update(values)
        _write_metadata(metadata)
        return metadata


def revise_transcript(recording_id: str, **values) -> dict:
    with _LOCK:
        metadata = get(recording_id)
        history = metadata.setdefault('transcript_history', [])
        history.append({
            'superseded_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'transcript_ta': metadata.get('transcript_ta'),
            'transcript_raw_ta': metadata.get('transcript_raw_ta'),
            'language': metadata.get('language'),
            'asr_flags': metadata.get('asr_flags'),
            'asr_status': metadata.get('asr_status'),
            'asr_retried': metadata.get('asr_retried'),
        })
        metadata.update(values)
        _write_metadata(metadata)
        return metadata


def add_draft(recording_id: str, record_id: str, tamil: str, english: str) -> None:
    with _LOCK:
        metadata = get(recording_id)
        metadata['drafts'].append({
            'record_id': record_id,
            'created_at': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'transcript_sha256': hashlib.sha256(tamil.encode('utf-8')).hexdigest(),
            'translation_sha256': hashlib.sha256(english.encode('utf-8')).hexdigest(),
        })
        _write_metadata(metadata)


def list_recordings() -> list[dict]:
    root = _ensure_dir()
    items = []
    for path in root.glob('*.json'):
        try:
            item = get(path.stem)
        except HTTPException:
            continue
        items.append(item)
    return sorted(items, key=lambda item: item['created_at'], reverse=True)


def public_metadata(metadata: dict) -> dict:
    return {
        'id': metadata['id'],
        'created_at': metadata['created_at'],
        'original_filename': metadata['original_filename'],
        'content_type': metadata['content_type'],
        'size_bytes': metadata['size_bytes'],
        'sha256': metadata['sha256'],
        'status': metadata['status'],
        'duration_seconds': metadata.get('duration_seconds'),
        'audio_url': f"/v1/recordings/{metadata['id']}/audio",
        'drafts': metadata.get('drafts', []),
    }
