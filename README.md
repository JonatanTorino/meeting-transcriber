# Meeting Transcriber

An automated pipeline that converts meeting recordings into transcripts. Drop a video or audio file in — get a text file out.

```
media file → AudioExtractor → WAV → Transcriber → transcript + metadata
```

## Components

### [AudioExtractor](AudioExtractor/README.md)

A .NET 9 Windows background service. Watches a directory for media files, extracts the audio track using FFmpeg, and produces a normalized WAV (16 kHz, Mono, PCM 16-bit) ready for transcription.

### [Transcriber](Transcriber/README.md)

A Python service. Picks up WAV files from AudioExtractor's output directory and transcribes them using one of three Whisper backends (faster-whisper, openai-whisper, whisper-cpp). Outputs TXT, SRT, VTT, or JSON plus per-file performance and quality metrics.

## Requirements

- .NET 9 SDK (AudioExtractor)
- Python 3.10+ (Transcriber)
- Windows 10/11
- Internet access on first run (FFmpeg auto-download)

## Pipeline Flow

```
{RootPath}/input/     ← drop media files here (AudioExtractor watches this)
{RootPath}/output/    ← WAV files (Transcriber's input)
{RootPath}/processed/ ← original files after successful extraction
{RootPath}/failed/    ← failed files + .log sidecars

Transcriber/transcriptions/ ← output transcripts (.txt / .srt / .vtt / .json)
Transcriber/metadata/       ← per-transcription .meta.json files
```
