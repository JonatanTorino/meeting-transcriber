# Configuration Reference

All settings live under the `Pipeline` section in `appsettings.json`.

## Minimal configuration (RootPath only)

```json
{
  "Pipeline": {
    "RootPath": "C:\\MeetingTranscriber"
  }
}
```

Subdirectories `input`, `output`, `processed` and `failed` are derived automatically.

## Full configuration (all paths explicit)

```json
{
  "Pipeline": {
    "InputPath":     "D:\\watch\\incoming",
    "OutputPath":    "D:\\watch\\wav",
    "ProcessedPath": "D:\\watch\\done",
    "FailedPath":    "D:\\watch\\errors",
    "Extensions":    [ ".mp4", ".mkv", ".mp3", ".m4a" ],
    "RetryCount":    5,
    "RetryDelayMs":  1000
  }
}
```

When individual paths are specified they **always take precedence** over the derived `RootPath` values.

## Options

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `RootPath` | `string?` | `null` | Base directory. Subdirs are derived automatically. |
| `InputPath` | `string?` | `{RootPath}/input` | Directory to monitor. |
| `OutputPath` | `string?` | `{RootPath}/output` | WAV output directory. |
| `ProcessedPath` | `string?` | `{RootPath}/processed` | Successful originals are moved here. |
| `FailedPath` | `string?` | `{RootPath}/failed` | Failed files + `.log` sidecars land here. |
| `Extensions` | `string[]` | See below | File extensions to watch (case-insensitive). |
| `RetryCount` | `int` | `5` | How many times to retry a locked file before skipping. |
| `RetryDelayMs` | `int` | `1000` | Milliseconds between lock retries. |

### Default Extensions

`.mp3` `.mp4` `.mkv` `.wav` `.m4a` `.mov` `.avi` `.webm`

## Validation Rules

- At least one of `RootPath` **or** all four individual paths must be set.
- `Extensions` must not be empty.
- `RetryCount` and `RetryDelayMs` must be ≥ 0.

Invalid configuration prevents the service from starting and logs a clear error message.

## Environment-specific overrides

Use `appsettings.{Environment}.json` or environment variables to override settings without touching the base file:

```bash
# PowerShell
$env:Pipeline__RootPath = "E:\transcriber"
dotnet run
```
