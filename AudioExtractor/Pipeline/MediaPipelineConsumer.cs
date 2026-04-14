using AudioExtractor.Audio;
using AudioExtractor.Configuration;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using System.Threading.Channels;

namespace AudioExtractor.Pipeline;

public class MediaPipelineConsumer : BackgroundService
{
    private readonly PipelineOptions _options;
    private readonly Channel<string> _queue;
    private readonly IAudioExtractor _extractor;
    private readonly FailedFileHandler _failedHandler;
    private readonly ILogger<MediaPipelineConsumer> _logger;

    public MediaPipelineConsumer(
        IOptions<PipelineOptions> options,
        Channel<string> queue,
        IAudioExtractor extractor,
        FailedFileHandler failedHandler,
        ILogger<MediaPipelineConsumer> logger)
    {
        _options = options.Value;
        _queue = queue;
        _extractor = extractor;
        _failedHandler = failedHandler;
        _logger = logger;
    }

    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        _logger.LogInformation("Consumer started. Waiting for files...");

        await foreach (var filePath in _queue.Reader.ReadAllAsync(stoppingToken))
        {
            await ProcessAsync(filePath, stoppingToken);
        }

        _logger.LogInformation("Consumer stopped.");
    }

    private async Task ProcessAsync(string sourcePath, CancellationToken ct)
    {
        _logger.LogInformation("Processing: {File}", sourcePath);

        var baseName = Path.GetFileNameWithoutExtension(sourcePath);
        var outputPath = Path.Combine(_options.ResolvedOutputPath, baseName + ".wav");

        try
        {
            await _extractor.ExtractAsync(sourcePath, outputPath, ct);

            var destPath = Path.Combine(_options.ResolvedProcessedPath, Path.GetFileName(sourcePath));
            File.Move(sourcePath, destPath, overwrite: true);

            _logger.LogInformation("Done. WAV → {Output} | Source → {Processed}", outputPath, destPath);
        }
        catch (OperationCanceledException)
        {
            _logger.LogWarning("Processing cancelled for: {File}", sourcePath);
        }
        catch (Exception ex)
        {
            _logger.LogError(ex, "Extraction failed for: {File}", sourcePath);
            await _failedHandler.HandleAsync(sourcePath, ex);
        }
    }
}
