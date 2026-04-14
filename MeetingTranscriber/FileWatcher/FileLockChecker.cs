using MeetingTranscriber.Configuration;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace MeetingTranscriber.FileWatcher;

public class FileLockChecker
{
    private readonly PipelineOptions _options;
    private readonly ILogger<FileLockChecker> _logger;

    public FileLockChecker(IOptions<PipelineOptions> options, ILogger<FileLockChecker> logger)
    {
        _options = options.Value;
        _logger = logger;
    }

    /// <summary>
    /// Waits until the file at <paramref name="filePath"/> is no longer locked.
    /// Returns normally when the file is accessible.
    /// Throws <see cref="IOException"/> after <see cref="PipelineOptions.RetryCount"/> failed attempts.
    /// </summary>
    public async Task WaitUntilUnlockedAsync(string filePath, CancellationToken ct = default)
    {
        for (int attempt = 1; attempt <= _options.RetryCount; attempt++)
        {
            if (IsAccessible(filePath))
                return;

            _logger.LogWarning(
                "File locked (attempt {Attempt}/{Max}): {File}",
                attempt, _options.RetryCount, filePath);

            await Task.Delay(_options.RetryDelayMs, ct);
        }

        throw new IOException(
            $"File remained locked after {_options.RetryCount} attempts: {filePath}");
    }

    private static bool IsAccessible(string filePath)
    {
        try
        {
            using var stream = File.Open(filePath, FileMode.Open, FileAccess.Read, FileShare.None);
            return true;
        }
        catch (IOException)
        {
            return false;
        }
    }
}
