using MeetingTranscriber.Configuration;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Options;
using Xabe.FFmpeg;

namespace MeetingTranscriber.Audio;

public class AudioExtractor : IAudioExtractor
{
    private readonly PipelineOptions _options;
    private readonly ILogger<AudioExtractor> _logger;

    public AudioExtractor(IOptions<PipelineOptions> options, ILogger<AudioExtractor> logger)
    {
        _options = options.Value;
        _logger = logger;
    }

    public async Task ExtractAsync(string sourcePath, string outputPath, CancellationToken ct = default)
    {
        _logger.LogInformation("Extracting audio: {Source} → {Output}", sourcePath, outputPath);

        IMediaInfo mediaInfo = await FFmpeg.GetMediaInfo(sourcePath, ct);

        var audioStream = mediaInfo.AudioStreams.FirstOrDefault()
            ?? throw new InvalidOperationException($"No audio track found in: {sourcePath}");

        audioStream
            .SetSampleRate(16000)
            .SetChannels(1);

        var conversion = FFmpeg.Conversions.New()
            .AddStream(audioStream)
            .AddParameter("-acodec pcm_s16le")
            .SetOutput(outputPath)
            .SetOverwriteOutput(true);

        await conversion.Start(ct);

        _logger.LogInformation("Extraction complete: {Output}", outputPath);
    }
}
