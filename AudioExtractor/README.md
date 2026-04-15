# AudioExtractor

A .NET 9 Windows background service that watches a directory for audio/video files and extracts the audio as a **WAV (16 kHz, Mono, PCM 16-bit)** — optimised for Whisper transcription.

## Quick Start

1. **Configure** the root directory in `appsettings.json`:
   ```json
   "Pipeline": {
     "RootPath": "C:\\MeetingTranscriber"
   }
   ```
   The service auto-creates `input/`, `output/`, `processed/`, and `failed/` inside that root.

2. **Run**:
   ```bash
   dotnet run
   ```
   On first launch the service downloads FFmpeg binaries automatically into `tools/ffmpeg/`.

3. **Drop a file** into `{RootPath}/input/`. The service detects it, converts it, and:
   - Writes the WAV to `{RootPath}/output/{same-name}.wav`
   - Moves the source to `{RootPath}/processed/`

4. On **failure**, the source moves to `{RootPath}/failed/` with a sidecar `{filename}.log` containing the full error and stack trace.

## Directory Layout

```
{RootPath}/
├── input/          ← drop media files here
├── output/         ← WAV files land here
├── processed/      ← successfully converted originals
└── failed/         ← files that failed + .log sidecars
```

## Requirements

- .NET 9 SDK
- Windows 10/11
- Internet access on first run (FFmpeg auto-download)

## Further Reading

- [Configuration reference](docs/configuration.md)
- [Architecture overview](docs/architecture.md)
