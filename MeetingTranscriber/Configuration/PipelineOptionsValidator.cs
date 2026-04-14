using Microsoft.Extensions.Options;

namespace MeetingTranscriber.Configuration;

public class PipelineOptionsValidator : IValidateOptions<PipelineOptions>
{
    public ValidateOptionsResult Validate(string? name, PipelineOptions options)
    {
        var errors = new List<string>();

        if (options.RootPath is null
            && options.InputPath is null
            && options.OutputPath is null
            && options.ProcessedPath is null
            && options.FailedPath is null)
        {
            errors.Add(
                "Pipeline configuration error: set 'RootPath' to derive all directories automatically, " +
                "or specify each path (InputPath, OutputPath, ProcessedPath, FailedPath) individually.");
        }

        if (options.RootPath is null)
        {
            if (options.InputPath is null)     errors.Add("'InputPath' is required when 'RootPath' is not set.");
            if (options.OutputPath is null)    errors.Add("'OutputPath' is required when 'RootPath' is not set.");
            if (options.ProcessedPath is null) errors.Add("'ProcessedPath' is required when 'RootPath' is not set.");
            if (options.FailedPath is null)    errors.Add("'FailedPath' is required when 'RootPath' is not set.");
        }

        if (options.Extensions is null || options.Extensions.Length == 0)
            errors.Add("'Extensions' must contain at least one entry.");

        if (options.RetryCount < 0)
            errors.Add("'RetryCount' must be >= 0.");

        if (options.RetryDelayMs < 0)
            errors.Add("'RetryDelayMs' must be >= 0.");

        return errors.Count > 0
            ? ValidateOptionsResult.Fail(errors)
            : ValidateOptionsResult.Success;
    }
}
