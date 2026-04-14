using MeetingTranscriber.Configuration;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;

namespace MeetingTranscriber.Pipeline;

public class FailedFileHandler
{
    private readonly PipelineOptions _options;
    private readonly ILogger<FailedFileHandler> _logger;

    public FailedFileHandler(IOptions<PipelineOptions> options, ILogger<FailedFileHandler> logger)
    {
        _options = options.Value;
        _logger = logger;
    }

    /// <summary>
    /// Moves <paramref name="sourcePath"/> to the configured failed directory and
    /// writes a sidecar <c>{basename}.log</c> containing error details.
    /// </summary>
    public async Task HandleAsync(string sourcePath, Exception ex)
    {
        var failedDir = _options.ResolvedFailedPath;
        var baseName = Path.GetFileNameWithoutExtension(sourcePath);
        var fileName = Path.GetFileName(sourcePath);

        var destFilePath = Path.Combine(failedDir, fileName);
        var logFilePath = Path.Combine(failedDir, baseName + ".log");

        // Move source to /failed.
        try
        {
            File.Move(sourcePath, destFilePath, overwrite: true);
            _logger.LogWarning("Moved failed file to: {Dest}", destFilePath);
        }
        catch (Exception moveEx)
        {
            _logger.LogError(moveEx, "Could not move failed file: {Source}", sourcePath);
        }

        // Write sidecar log.
        var content =
            $"Timestamp  : {DateTimeOffset.Now:O}\n" +
            $"Source     : {sourcePath}\n" +
            $"Error      : {ex.GetType().FullName}: {ex.Message}\n\n" +
            $"StackTrace :\n{ex.StackTrace}\n";

        if (ex.InnerException is not null)
        {
            content +=
                $"\nInnerException: {ex.InnerException.GetType().FullName}: {ex.InnerException.Message}\n" +
                $"{ex.InnerException.StackTrace}\n";
        }

        try
        {
            await File.WriteAllTextAsync(logFilePath, content);
            _logger.LogWarning("Error log written: {Log}", logFilePath);
        }
        catch (Exception logEx)
        {
            _logger.LogError(logEx, "Could not write error log: {Log}", logFilePath);
        }
    }
}
