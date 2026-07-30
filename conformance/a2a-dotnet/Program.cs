// A2A agent on the official .NET SDK, to check Beacon against a fifth
// independent implementation.
//
//   cd conformance/a2a-dotnet && dotnet run
//
//   python3 -m beacon a2a-inspect http://127.0.0.1:8791 --send hello
//
// Found no defects, which is the point of running it: by this SDK the client
// had stopped diverging.

using A2A;
using A2A.AspNetCore;

// Reference A2A agent on the official .NET SDK, for checking Beacon's client.
const string Base = "http://127.0.0.1:8791";

var builder = WebApplication.CreateBuilder(args);
builder.Logging.SetMinimumLevel(LogLevel.Warning);
builder.WebHost.UseUrls(Base);
builder.Services.AddA2AAgent<ReferenceAgent>(ReferenceAgent.GetAgentCard(Base + "/"));

var app = builder.Build();
app.MapA2A("/");
app.MapWellKnownAgentCard(app.Services.GetRequiredService<AgentCard>());
Console.WriteLine($".NET reference agent on {Base}");
app.Run();

public sealed class ReferenceAgent : IAgentHandler
{
    public async Task ExecuteAsync(RequestContext context, AgentEventQueue eventQueue,
        CancellationToken cancellationToken)
    {
        var text = context.UserText ?? "";
        if (text.Length > 200) text = text[..200];
        var responder = new MessageResponder(eventQueue, context.ContextId);
        await responder.ReplyAsync($"REFERENCE-AGENT-DOTNET-SAW: {text}",
            cancellationToken: cancellationToken);
    }

    public static AgentCard GetAgentCard(string agentUrl) => new()
    {
        Name = "Beacon reference A2A agent (.NET)",
        Description = "Official A2A .NET SDK agent used to check Beacon's A2A client.",
        Version = "1.0.0",
        SupportedInterfaces =
        [
            new AgentInterface
            {
                Url = agentUrl,
                ProtocolBinding = "JSONRPC",
                ProtocolVersion = "1.0",
            }
        ],
        DefaultInputModes = ["text/plain"],
        DefaultOutputModes = ["text/plain"],
        Capabilities = new AgentCapabilities { Streaming = false, PushNotifications = false },
        Skills =
        [
            new AgentSkill
            {
                Id = "echo", Name = "echo",
                Description = "Echoes its input.", Tags = ["test"],
            }
        ],
    };
}
