# Architecture Overview

## Pattern: Producer–Consumer

The pipeline is split into two independent halves connected by a bounded in-memory queue.

```
┌─────────────────────────────────────────────────────────────────────────┐
│  FileWatcherService  (Producer — BackgroundService)                     │
│                                                                         │
│   FileSystemWatcher                                                     │
│   └─ Created event ──► extension filter ──► FileLockChecker            │
│                                                    │                    │
│                                              retry (N × delay)          │
│                                                    │                    │
│                                              Channel<string>            │
│                                            (bounded, cap=100)           │
└──────────────────────────────────────────────────┬──────────────────────┘
                                                   │
                                            WriteAsync()
                                                   │
                                                   ▼
┌─────────────────────────────────────────────────────────────────────────┐
│  MediaPipelineConsumer  (Consumer — BackgroundService)                  │
│                                                                         │
│   ReadAllAsync()                                                        │
│       │                                                                 │
│       ▼                                                                 │
│   AudioExtractor (Xabe.FFmpeg)                                         │
│   └─ ffmpeg -i src -ar 16000 -ac 1 -acodec pcm_s16le out.wav          │
│         │                                                               │
│    ┌────┴────┐                                                          │
│  success   failure                                                      │
│    │           │                                                        │
│    ▼           ▼                                                        │
│  Move to   FailedFileHandler                                            │
│ /processed  ├─ move source → /failed                                   │
│             └─ write {name}.log (timestamp + stack trace)              │
└─────────────────────────────────────────────────────────────────────────┘
```

## Component Diagram

```
┌──────────────┐     Channel<string>     ┌────────────────────────┐
│ FileWatcher  │ ──────────────────────► │ MediaPipelineConsumer  │
│   Service    │                         └──────────┬─────────────┘
└──────┬───────┘                                    │
       │                                   ┌────────┴────────┐
       │                                   │                 │
       ▼                                   ▼                 ▼
┌─────────────┐                    ┌──────────────┐  ┌──────────────┐
│  FileLock   │                    │  Audio       │  │  Failed      │
│  Checker    │                    │  Extractor   │  │  File Handler│
└─────────────┘                    └──────────────┘  └──────────────┘
                                          │
                                          ▼
                                   ┌──────────────┐
                                   │ Xabe.FFmpeg  │
                                   │  (ffmpeg.exe)│
                                   └──────────────┘
```

## File Lifecycle State Machine

```
                  ┌──────────┐
                  │  /input  │  ◄── FileSystemWatcher detects
                  └────┬─────┘
                       │  lock check OK
                       │  enqueued → consumer picks up
                       │
                       ▼
              ┌─────────────────┐
              │  AudioExtractor │
              └────────┬────────┘
                       │
             ┌─────────┴──────────┐
             │ success            │ failure
             ▼                    ▼
      ┌────────────┐       ┌────────────┐
      │ /processed │       │  /failed   │
      └────────────┘       │  + .log    │
                           └────────────┘
```

## Technology Decisions

| Concern | Choice | Reason |
|---------|--------|--------|
| App hosting | .NET 9 Worker Service (Generic Host) | Headless, Windows Service-compatible, DI + config built in |
| Queue | `Channel<string>` bounded | Async-native, backpressure via `FullMode = Wait`, no extra dependencies |
| Audio extraction | Xabe.FFmpeg + FFmpeg binary | Handles all formats; auto-download on first run |
| Configuration | `appsettings.json` + `IOptions<T>` | Standard .NET pattern; validated at startup |
| Logging | Serilog | Structured logs; rolls daily; sinks to console + file |

## Startup Sequence

1. Bootstrap Serilog (before host, captures early errors)
2. Check / download FFmpeg binaries into `tools/ffmpeg/`
3. Build Generic Host — bind and validate `PipelineOptions`
4. Create pipeline directories (input, output, processed, failed)
5. Start `FileWatcherService` — scans existing files, starts watcher
6. Start `MediaPipelineConsumer` — begins draining the queue
7. Process files until CTRL+C / service stop signal
