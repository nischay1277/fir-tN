# Tamil Speech to FIR Drafting

**Stack:** Python, FastAPI, Pydantic, Whisper, LangGraph, React, TypeScript.

**Workflow:** Transcribe Tamil or mixed Tamil-English audio, extract structured complaint facts, and review a deterministic IF-1 draft with source evidence. Candidate statutory sections remain suggestions for human review.

An officer-assisted prototype for turning Tamil or Tamil-English complaints into structured facts, candidate statutory sections, clarification questions, and an IF-1-style draft. It includes a FastAPI backend, LangGraph orchestration, and a React/TypeScript review interface.

This repository provides a drafting and review aid. It does not register an FIR or connect to police filing systems. Candidate provisions and generated fields require officer review; this is not a claim of deployment or endorsement by Tamil Nadu Police.

## How it works

```text
Audio -> Tamil transcription + separate English speech translation
                         |
Text complaint ----------+-> extract facts -> translate when available
  -> predict IPC candidates -> map to BNS with review flags
  -> check schedule-based cognizability -> build evidence/clarification graph
  -> create structured record -> render IF-1 text/Markdown -> officer review
```

### Implemented components

- **Speech:** `faster-whisper`, configured with `Systran/faster-whisper-large-v3`, language handling, quality flags, and transcript retry support.
- **Translation:** speech translation through Whisper; optional cached text translation using the model configured in `configs/pipeline.yaml` (default `Helsinki-NLP/opus-mt-dra-en`).
- **Classification:** TF-IDF/hashing features plus one-vs-rest logistic regression when a trained artifact is supplied. A rule-cue classifier is available as the automatic fallback.
- **Statutory processing:** local IPC-to-BNS mappings, BNS text, BNSS schedule data, offence cues, and review flags.
- **Drafting:** Pydantic records, extracted spans, deterministic rendering, evidence links, and clarification questions.
- **Review interface:** recording upload/history, transcript review, structured draft preview, and clarification submission.
- **Local storage:** recordings with metadata and hashes; JSONL draft audit entries.

The current implementation is a speech/classification/rules workflow. It is not a hosted generative-LLM chatbot or a vector-database RAG service.

## Requirements

- Python **3.11 to 3.13**, as specified in `pyproject.toml`.
- `uv` for the checked-in lockfile workflow, or pip for editable installation.
- Node.js **20.19.x or newer within 20.x, or 22.12+**, matching the locked Vite 8 engine range (`^20.19.0 || >=22.12.0`), and npm for the frontend.
- Network access for dependency and initial speech-model downloads. The large speech model requires substantial disk space and memory; CPU inference may be slow.

Run from a repository checkout. Runtime configuration/data paths are resolved relative to `src/fir/config.py`, so a standalone installed wheel is not sufficient without the repository's `configs/` and `data/` directories.

## Start the application

```bash
git clone https://github.com/nischay1277/fir-tN.git
cd fir-tN
uv sync --extra full
```

In one terminal, start the backend:

```bash
uv run --extra full uvicorn fir.serving.app:app --host 127.0.0.1 --port 8000
```

In another terminal, start the frontend:

```bash
cd frontend
npm ci
npm run dev -- --host 127.0.0.1 --port 5173
```

- Interface: **http://127.0.0.1:5173/**
- API documentation: **http://127.0.0.1:8000/docs**
- Health and startup errors: **http://127.0.0.1:8000/v1/health**
- Available capabilities: **http://127.0.0.1:8000/v1/capabilities**

On a Bash-compatible system, `bash start.sh` launches both services after dependencies are installed. The Makefile provides equivalent targets. Windows users can use the two-terminal commands directly.

### Serve a built frontend

```bash
cd frontend
npm ci
npm run build
cd ..
uv run --extra full uvicorn fir.serving.app:app --host 127.0.0.1 --port 8000
```

Restart the backend after building the frontend, then open **http://127.0.0.1:8000/**. The frontend development server proxies `/v1` requests to the backend.

## Text-only path and CLI

To install the API and legal workflow without the full speech dependency set:

```bash
uv sync --extra legal
uv run --extra legal tn-fir check
uv run --extra legal tn-fir draft "A person took my mobile phone near the bus stand."
```

The `draft` command accepts a text argument or standard input and prints a JSON result with the decision, structured record, rendered draft, and errors. For a first smoke check, an English synthetic complaint avoids requiring a cached Tamil-to-English translation model.

API example:

```bash
curl -X POST http://127.0.0.1:8000/v1/complaint/text -H "Content-Type: application/json" -d '{"narrative":"A person took my mobile phone near the bus stand.","annotate":true}'
```

On Windows PowerShell use `curl.exe` for this command, or submit the JSON body through `/docs`.

## Models, data, and degraded operation

- A trained classifier is **not included**: `artifacts/models/` contains only a placeholder. `registry.load('auto')` uses rule cues unless `artifacts/models/tfidf_statute.joblib` exists. The reported active classifier is visible in capabilities.
- The TF-IDF implementation supports training/loading, but no ready-to-run training CLI or bundled ILSI training split is committed. File names expected by the data loader are listed in `configs/datasets.yaml`.
- Legal reference files are included under `data/mapping/` and `data/statutes/`; inspect their provenance and coverage before interpreting candidate sections.
- Text translation requires locally cached model files. Its loader uses `local_files_only=True`; installing packages alone does not make that model available. For example, after installing the full extras, populate the cache explicitly with `uv run --extra full hf download Helsinki-NLP/opus-mt-dra-en`.
- Startup attempts to warm speech and drafting components and records failures rather than making every capability mandatory. Inspect `/v1/health` for `degraded` status and model errors. Capability flags are readiness hints, not measured accuracy.
- Change ASR/translation settings in `configs/pipeline.yaml`; classifier and mapping settings are also defined there.

## API surface

| Endpoint | Purpose |
| --- | --- |
| `GET /v1/health`, `GET /v1/capabilities` | Runtime status and available components |
| `POST /v1/speech/process` | Upload audio (multipart field `file`, maximum 25 MiB) |
| `GET /v1/recordings` | Recording list |
| `GET /v1/recordings/{recording_id}` | Recording metadata and transcript state |
| `GET /v1/recordings/{recording_id}/audio` | Replay stored audio |
| `POST /v1/recordings/{recording_id}/retry-transcript` | Retry transcription |
| `POST /v1/translate/text` | Optional local text translation |
| `POST /v1/complaint/text` | Analyze a text complaint and create a draft |
| `POST /v1/complaint/clarify` | Reanalyze with officer clarifications |
| `GET /v1/schema/if1` | IF-1 JSON schema |

## Storage and limits

`FIR_RECORDINGS_DIR` overrides the recording directory. Otherwise recordings are stored under `$XDG_DATA_HOME/tn-fir-speech/recordings`, or `~/.local/share/tn-fir-speech/recordings`. On Windows this fallback is under the user's home directory. Audio and transcript metadata remain on disk until manually managed; there is no retention scheduler.

`FIR_AUDIT_LOG` overrides the draft audit JSONL path; the default is `artifacts/audit/drafts.jsonl`. An empty value disables that audit writer. Draft audit entries include narrative hashes rather than full narratives, while recording metadata can contain full transcripts.

The API has no authentication/authorization layer. Keep the prototype on loopback and use synthetic or appropriately consented inputs. Readiness checks do not establish legal correctness, and no automated tests or measured speech/classification benchmark results are committed in this snapshot.

## Layout

```text
configs/           Model, pipeline, and dataset configuration
data/              Local statutory text, schedules, and mappings
frontend/          React/TypeScript review interface
src/fir/asr/       Speech decoding and quality checks
src/fir/translate/ Optional local text translation
src/fir/statute/   Classification, mapping, and evidence rules
src/fir/extract/   Fact extraction and field filling
src/fir/instantiate/  Draft record and rendering
src/fir/orchestrator/ LangGraph workflow
src/fir/serving/   API, recordings, and audit storage
```
