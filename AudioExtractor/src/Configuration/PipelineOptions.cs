namespace AudioExtractor.Configuration;

public class PipelineOptions
{
    public const string SectionName = "Pipeline";

    /// <summary>
    /// Base directory for all pipeline folders.
    /// When set, Input/Output/Processed/Failed paths default to subdirectories of this root.
    /// Individual paths always take precedence over the derived value.
    /// </summary>
    public string? RootPath { get; set; }

    /// <summary>Monitored input directory. Defaults to {RootPath}/input.</summary>
    public string? InputPath { get; set; }

    /// <summary>WAV output directory. Defaults to {RootPath}/output.</summary>
    public string? OutputPath { get; set; }

    /// <summary>Destination for successfully processed source files. Defaults to {RootPath}/processed.</summary>
    public string? ProcessedPath { get; set; }

    /// <summary>Destination for failed source files + sidecar .log. Defaults to {RootPath}/failed.</summary>
    public string? FailedPath { get; set; }

    /// <summary>File extensions to watch (include the dot, e.g. ".mp4").</summary>
    public string[] Extensions { get; set; } =
        [".mp3", ".mp4", ".mkv", ".wav", ".m4a", ".mov", ".avi", ".webm"];

    /// <summary>Number of retry attempts when a file is locked by another process.</summary>
    public int RetryCount { get; set; } = 5;

    /// <summary>Delay in milliseconds between lock-check retries.</summary>
    public int RetryDelayMs { get; set; } = 1000;

    public string ResolvedInputPath => Resolve(InputPath, "input");
    public string ResolvedOutputPath => Resolve(OutputPath, "output");
    public string ResolvedProcessedPath => Resolve(ProcessedPath, "processed");
    public string ResolvedFailedPath => Resolve(FailedPath, "failed");

    private string Resolve(string? explicitPath, string subfolder)
    {
        if (explicitPath is not null)
            return explicitPath;

        if (RootPath is not null)
            return Path.Combine(RootPath, subfolder);

        throw new InvalidOperationException(
            $"Pipeline configuration is missing: either set 'RootPath' or explicitly set the '{subfolder}' path.");
    }
}
