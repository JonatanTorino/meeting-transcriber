namespace MeetingTranscriber.Audio;

public interface IAudioExtractor
{
    /// <summary>
    /// Extracts the audio track from <paramref name="sourcePath"/> and writes a
    /// WAV file (16 kHz, Mono, PCM 16-bit) to <paramref name="outputPath"/>.
    /// Throws <see cref="InvalidOperationException"/> if the source has no audio track.
    /// </summary>
    Task ExtractAsync(string sourcePath, string outputPath, CancellationToken ct = default);
}
