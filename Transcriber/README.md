# Transcriber

A Python service that picks up WAV files produced by AudioExtractor and transcribes them using one of three interchangeable Whisper backends. Outputs TXT, SRT, VTT, or JSON plus a per-file `.meta.json` with performance and quality metrics.

## Quick Start

1. **Install dependencies**:
   ```bash
   pip install -r src/requirements.txt
   ```

2. **Configure** `src/config.yaml`:
   ```yaml
   default_implementation: faster-whisper-turbo
   default_format: txt

   paths:
     input: ../AudioExtractor/output
     transcriptions: ./transcriptions
     metadata: ./metadata
   ```

3. **Run**:

   ```bash
   # Watcher mode — monitors input/ and transcribes new WAV files automatically
   python src/watcher.py

   # One-shot mode — transcribe a specific file
   python src/transcribe.py path/to/audio.wav
   python src/transcribe.py audio.wav --impl whisper-cpp-medium --format srt
   ```

## Directory Layout

```
Transcriber/
├── src/
│   ├── config.yaml         ← runtime configuration
│   ├── watcher.py          ← continuous service (event-driven)
│   ├── transcribe.py       ← one-shot CLI
│   ├── engine/             ← Whisper backend adapters (Strategy Pattern)
│   ├── formatters.py       ← TXT / SRT / VTT / JSON writers
│   └── metadata.py         ← per-transcription .meta.json builder
├── transcriptions/         ← output transcripts (auto-created)
└── metadata/               ← output .meta.json sidecars (auto-created)
```

## Engines

| Engine | Backend | GPU | VAD | Notes |
|--------|---------|-----|-----|-------|
| `faster-whisper` | CTranslate2 | cuda | yes | Default — fastest on CPU with INT8 |
| `openai-whisper` | PyTorch | cuda | no | Reference implementation |
| `whisper-cpp` | GGML/C++ | no | no | CPU-only; no quality metrics |

## Requirements

- Python 3.10+
- See `src/requirements.txt` for dependencies

## Further Reading

- [Configuration reference](docs/configuration.md)
- [Architecture overview](docs/architecture.md)
