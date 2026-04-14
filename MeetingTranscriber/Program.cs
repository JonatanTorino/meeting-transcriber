using MeetingTranscriber.Audio;
using MeetingTranscriber.Configuration;
using MeetingTranscriber.FileWatcher;
using MeetingTranscriber.Pipeline;
using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Hosting;
using Microsoft.Extensions.Options;
using Serilog;
using System.Threading.Channels;
using Xabe.FFmpeg;
using Xabe.FFmpeg.Downloader;

// ── Bootstrap Serilog (before host build so startup errors are captured) ──────
Log.Logger = new LoggerConfiguration()
    .MinimumLevel.Information()
    .WriteTo.Console(outputTemplate: "[{Timestamp:HH:mm:ss} {Level:u3}] {Message:lj}{NewLine}{Exception}")
    .WriteTo.File(
        Path.Combine(AppContext.BaseDirectory, "logs", "pipeline-.log"),
        rollingInterval: RollingInterval.Day,
        outputTemplate: "{Timestamp:yyyy-MM-dd HH:mm:ss.fff zzz} [{Level:u3}] {Message:lj}{NewLine}{Exception}")
    .CreateBootstrapLogger();

try
{
    Log.Information("Meeting Transcriber starting up...");

    // ── Ensure FFmpeg binaries are available ─────────────────────────────────
    var ffmpegDir = Path.Combine(AppContext.BaseDirectory, "tools", "ffmpeg");
    Directory.CreateDirectory(ffmpegDir);
    FFmpeg.SetExecutablesPath(ffmpegDir);

    if (!File.Exists(Path.Combine(ffmpegDir, "ffmpeg.exe")))
    {
        Log.Information("FFmpeg not found at {Dir}. Downloading — this runs once only...", ffmpegDir);
        await FFmpegDownloader.GetLatestVersion(FFmpegVersion.Official, ffmpegDir);
        Log.Information("FFmpeg downloaded successfully.");
    }

    // ── Build and run the Generic Host ───────────────────────────────────────
    var host = Host.CreateDefaultBuilder(args)
        .UseSerilog((_, _, cfg) => cfg
            .MinimumLevel.Information()
            .MinimumLevel.Override("Microsoft", Serilog.Events.LogEventLevel.Warning)
            .MinimumLevel.Override("Microsoft.Hosting.Lifetime", Serilog.Events.LogEventLevel.Information)
            .WriteTo.Console(outputTemplate: "[{Timestamp:HH:mm:ss} {Level:u3}] {Message:lj}{NewLine}{Exception}")
            .WriteTo.File(
                Path.Combine(AppContext.BaseDirectory, "logs", "pipeline-.log"),
                rollingInterval: RollingInterval.Day))
        .ConfigureServices((ctx, services) =>
        {
            // Configuration
            services
                .AddOptions<PipelineOptions>()
                .Bind(ctx.Configuration.GetSection(PipelineOptions.SectionName))
                .ValidateOnStart();

            services.AddSingleton<IValidateOptions<PipelineOptions>, PipelineOptionsValidator>();

            // Queue (bounded — 100 items, wait on full)
            services.AddSingleton(_ => Channel.CreateBounded<string>(
                new BoundedChannelOptions(100)
                {
                    FullMode = BoundedChannelFullMode.Wait,
                    SingleReader = true
                }));

            // Core components
            services.AddSingleton<FileLockChecker>();
            services.AddSingleton<FailedFileHandler>();
            services.AddSingleton<IAudioExtractor, AudioExtractor>();

            // Hosted services (producer + consumer)
            services.AddHostedService<FileWatcherService>();
            services.AddHostedService<MediaPipelineConsumer>();
        })
        .Build();

    // Ensure pipeline directories exist before starting.
    EnsureDirectories(host.Services);

    await host.RunAsync();
}
catch (Exception ex)
{
    Log.Fatal(ex, "Host terminated unexpectedly.");
    return 1;
}
finally
{
    await Log.CloseAndFlushAsync();
}

return 0;

// ── Helpers ───────────────────────────────────────────────────────────────────
static void EnsureDirectories(IServiceProvider services)
{
    var options = services.GetRequiredService<IOptions<PipelineOptions>>().Value;
    foreach (var dir in new[]
    {
        options.ResolvedInputPath,
        options.ResolvedOutputPath,
        options.ResolvedProcessedPath,
        options.ResolvedFailedPath
    })
    {
        Directory.CreateDirectory(dir);
        Log.Debug("Directory ensured: {Dir}", dir);
    }
}
