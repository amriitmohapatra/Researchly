using System;
using System.Threading;
using System.Threading.Tasks;
using Researchly.Overlay.Core.Engine;
using Researchly.Overlay.Core.Settings;

namespace Researchly.Overlay.Platform;

/// <summary>
/// The engine the writer chose, swappable at run time from the menu. When
/// "Hosted" has no address yet, every check fails with a clear next step
/// (the offline state's detail) instead of sending text anywhere.
/// </summary>
internal sealed class SwitchableEngine : IEngineClient, IDisposable
{
    private HttpEngineClient? _client;

    public void Configure(OverlaySettings settings, string version)
    {
        var old = _client;
        string? url = settings.EngineBaseUrl();
        _client = url == null ? null : new HttpEngineClient(url, userAgentVersion: version);
        old?.Dispose();
    }

    public Task<CheckReply> CheckAsync(CheckParagraphsRequest request, CancellationToken cancellationToken)
    {
        var client = _client;
        if (client == null)
            return Task.FromException<CheckReply>(new EngineException("no_engine", "Choose an engine in the Researchly menu."));
        return client.CheckAsync(request, cancellationToken);
    }

    public void Dispose() => _client?.Dispose();
}
