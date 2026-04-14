using MeetingTranscriber.Configuration;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using System.Threading.Channels;

namespace MeetingTranscriber.FileWatcher;

public class FileWatcherService : BackgroundService
{
    private readonly PipelineOptions _options;
    private readonly Channel<string> _queue;
    private readonly FileLockChecker _lockChecker;
    private readonly ILogger<FileWatcherService> _logger;

    public FileWatcherService(
        IOptions<PipelineOptions> options,
        Channel<string> queue,
        FileLockChecker lockChecker,
        ILogger<FileWatcherService> logger)
    {
        _options = options.Value;
        _queue = queue;
        _lockChecker = lockChecker;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var inputPath = _options.ResolvedInputPath;

        _logger.LogInformation("Watching directory: {InputPath}", inputPath);

        // Enqueue any files that already exist in the input directory at startup.
        await EnqueueExistingFilesAsync(inputPath, stoppingToken);

        using var watcher = new FileSystemWatcher(inputPath)
        {
            NotifyFilter = NotifyFilters.FileName | NotifyFilters.LastWrite,
            IncludeSubdirectories = false,
            EnableRaisingEvents = true
        };

        watcher.Created += (_, e) => OnFileCreated(e.FullPath, stoppingToken);

        // Keep alive until the host requests shutdown.
        await Task.Delay(Timeout.Infinite, stoppingToken).ConfigureAwait(false);
    }

    private void OnFileCreated(string fullPath, CancellationToken ct)
    {
        if (!IsWatchedExtension(fullPath))
        {
            _logger.LogDebug("Ignored (unsupported extension): {File}", fullPath);
            return;
        }

        // Fire-and-forget the lock check + enqueue so the watcher event returns immediately.
        _ = Task.Run(() => TryEnqueueAsync(fullPath, ct), ct);
    }

    private async Task TryEnqueueAsync(string fullPath, CancellationToken ct)
    {
        try
        {
            await _lockChecker.WaitUntilUnlockedAsync(fullPath, ct);
            await _queue.Writer.WriteAsync(fullPath, ct);
            _logger.LogInformation("Enqueued: {File}", fullPath);
        }
        catch (IOException ex)
        {
            _logger.LogError(ex, "Skipped (file remained locked): {File}", fullPath);
        }
        catch (OperationCanceledException)
        {
            // Host is shutting down — normal exit.
        }
    }

    private async Task EnqueueExistingFilesAsync(string inputPath, CancellationToken ct)
    {
        foreach (var file in Directory.EnumerateFiles(inputPath)
                     .Where(IsWatchedExtension))
        {
            _logger.LogInformation("Found existing file at startup: {File}", file);
            await TryEnqueueAsync(file, ct);
        }
    }

    private bool IsWatchedExtension(string path)
    {
        var ext = Path.GetExtension(path);
        return _options.Extensions.Contains(ext, StringComparer.OrdinalIgnoreCase);
    }
}
