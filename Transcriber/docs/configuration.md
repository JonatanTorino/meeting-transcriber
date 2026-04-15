# Configuration Reference — Transcriber

All settings live in `config.yaml` at the root of the `Transcriber/` directory.

---

## Minimal configuration

```yaml
default_implementation: faster-whisper-turbo
default_format: txt

paths:
  input: ../AudioExtractor/output
  transcriptions: ./transcriptions
  metadata: ./metadata
```

---

## Full reference

```yaml
# Which implementation the watcher uses by default.
# Must match a key under `implementations`.
default_implementation: faster-whisper-turbo

# Default output format when --format is not specified.
# Applies to both watcher.py and transcribe.py.
default_format: txt   # txt | srt | vtt | json

paths:
  # Directory where AudioExtractor drops the final .wav files.
  # The watcher monitors this directory for new arrivals.
  input: ../AudioExtractor/output

  # Directory where transcription output files are written.
  transcriptions: ./transcriptions

  # Directory where per-transcription .meta.json files are written.
  metadata: ./metadata

implementations:
  <impl-name>:
    engine:             faster-whisper | openai-whisper | whisper-cpp
    model:              <model name>   # see Engine options below
    device:             cpu | cuda
    compute_type:       int8 | float16 | float32   # faster-whisper only
    beam_size:          5              # faster-whisper / openai-whisper
    language:           es             # ISO 639-1 code
    vad_filter:         true           # faster-whisper only
    vad_min_silence_ms: 500            # faster-whisper only
    n_threads:          4              # whisper-cpp only
```

---

## Paths

| Key | Description | Default |
|-----|-------------|---------|
| `paths.input` | Directory watched for new `.wav` files | `../AudioExtractor/output` |
| `paths.transcriptions` | Transcription output files (`.txt`, `.srt`, etc.) | `./transcriptions` |
| `paths.metadata` | Per-transcription metadata JSON sidecars | `./metadata` |

Paths are resolved relative to `config.yaml`. Both relative and absolute paths are accepted.

---

## Engine options

### `faster-whisper` (recommended)

Uses CTranslate2. Fastest on CPU with INT8 quantization.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `model` | string | — | `tiny` · `small` · `medium` · `turbo` · `large-v3` |
| `device` | string | `cpu` | `cpu` or `cuda` |
| `compute_type` | string | `int8` | `int8` · `float16` · `float32` |
| `beam_size` | int | `5` | Beam search width. Higher = more accurate, slower. |
| `language` | string | `es` | ISO 639-1 language code. Forces language detection off. |
| `vad_filter` | bool | `true` | Skips silent segments before transcription. |
| `vad_min_silence_ms` | int | `500` | Minimum silence duration (ms) for VAD to trigger. |

### `openai-whisper`

Reference PyTorch implementation. Slowest on CPU (FP32 only), highest compatibility.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `model` | string | — | `tiny` · `small` · `medium` · `turbo` · `large-v3` |
| `device` | string | `cpu` | `cpu` only for most setups (FP16 unsupported on CPU) |
| `beam_size` | int | `5` | Beam search width. |
| `language` | string | `es` | ISO 639-1 language code. |

> **Note:** `language_probability` is not available with this engine — the metadata field will be `null`.

### `whisper-cpp`

GGML/SIMD C++ binary via `pywhispercpp`. 20–40% faster than faster-whisper in some CPU profiles.

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `model` | string | — | `tiny` · `small` · `medium` · `large-v3` |
| `language` | string | `es` | ISO 639-1 language code. |
| `n_threads` | int | `4` | CPU threads for inference. |

> **Note:** `language_probability`, `avg_logprob`, and `no_speech_prob` are not available with this engine — the metadata fields will be `null` or `0.0`.

---

## Pre-defined implementations

The following implementations are included out of the box and can be used directly with `--impl`:

| Key | Engine | Model | Notes |
|-----|--------|-------|-------|
| `faster-whisper-tiny` | faster-whisper | tiny | Fastest, lowest accuracy |
| `faster-whisper-small` | faster-whisper | small | Good for quick testing |
| `faster-whisper-medium` | faster-whisper | medium | Balanced |
| `faster-whisper-turbo` | faster-whisper | turbo | **Default** — best quality/speed ratio |
| `faster-whisper-large-v3` | faster-whisper | large-v3 | Highest accuracy, slowest |
| `openai-whisper-tiny` | openai-whisper | tiny | Reference impl |
| `openai-whisper-small` | openai-whisper | small | — |
| `openai-whisper-medium` | openai-whisper | medium | — |
| `openai-whisper-turbo` | openai-whisper | turbo | — |
| `whisper-cpp-tiny` | whisper-cpp | tiny | SIMD-optimized |
| `whisper-cpp-small` | whisper-cpp | small | — |
| `whisper-cpp-medium` | whisper-cpp | medium | — |
| `whisper-cpp-large-v3` | whisper-cpp | large-v3 | — |

---

## Output formats

| Format | Description |
|--------|-------------|
| `txt` | Plain text, one line per segment |
| `srt` | SubRip subtitles with timestamps |
| `vtt` | WebVTT subtitles with timestamps |
| `json` | Segment array with start, end, text, avg_logprob, no_speech_prob |

---

## Metadata sidecar

Every transcription writes a `<audio-name>.meta.json` to `paths.metadata`. Example:

```json
{
  "transcription_id": "3f2a1c...",
  "timestamp_start": "2026-04-15T10:23:01Z",
  "timestamp_end":   "2026-04-15T10:25:47Z",
  "source": {
    "file": "reunion-abril.wav",
    "duration_seconds": 3612.4,
    "size_bytes": 115593216
  },
  "engine": {
    "implementation": "faster-whisper-turbo",
    "model": "turbo",
    "device": "cpu",
    "compute_type": "int8"
  },
  "result": {
    "language_detected": "es",
    "language_probability": 0.9987,
    "segment_count": 312,
    "word_count": 4821,
    "output_format": "txt",
    "output_path": "/abs/path/to/transcriptions/reunion-abril.txt"
  },
  "performance": {
    "model_load_time_seconds": 3.21,
    "inference_time_seconds": 148.7,
    "realtime_factor": 24.3,
    "peak_memory_mb": 1842.0,
    "avg_cpu_percent": 87.4
  },
  "quality": {
    "avg_logprob": -0.312,
    "avg_no_speech_prob": 0.031,
    "low_confidence_segments": 4
  }
}
```

### Key metrics

| Field | Description |
|-------|-------------|
| `realtime_factor` | `audio_duration / inference_time`. A value of 24x means 24 min of audio processed per real minute. |
| `model_load_time_seconds` | First-call cost only. `0.0` when the model is already cached in memory (watcher mode). |
| `low_confidence_segments` | Segments with `avg_logprob < -0.5`. A high count suggests the model struggled — review the output. |
| `peak_memory_mb` | Process RSS peak during inference. Useful for sizing the host machine. |

---

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Automatic mode — watches input/ for new .wav files
python watcher.py
python watcher.py --impl faster-whisper-small      # override impl for this session

# Manual / test mode — transcribe a specific file
python transcribe.py audio.wav
python transcribe.py audio.wav --impl whisper-cpp-medium --format srt
python transcribe.py audio.wav --impl faster-whisper-large-v3 --format json --output ./results/
```
