package beacon;

import io.a2a.server.PublicAgentCard;
import io.a2a.server.agentexecution.AgentExecutor;
import io.a2a.server.agentexecution.RequestContext;
import io.a2a.server.tasks.AgentEmitter;
import io.a2a.spec.A2AError;
import io.a2a.spec.AgentCapabilities;
import io.a2a.spec.AgentCard;
import io.a2a.spec.AgentInterface;
import io.a2a.spec.AgentSkill;
import io.a2a.spec.TransportProtocol;
import io.a2a.spec.UnsupportedOperationError;
import jakarta.enterprise.context.ApplicationScoped;
import jakarta.enterprise.inject.Produces;

import java.util.Collections;
import java.util.List;

/**
 * A2A agent on the official Java SDK, to check Beacon against a fourth
 * independent implementation.
 *
 * <pre>
 *   cd conformance/a2a-java &amp;&amp; mvn quarkus:dev
 *   python3 -m beacon a2a-inspect http://127.0.0.1:8781 --send hello
 * </pre>
 *
 * Found no defects in Beacon. Getting it running took three: the published
 * artifacts are a package generation behind the documented examples
 * ({@code io.a2a} rather than {@code org.a2aproject.sdk}), AgentInterface is a
 * record rather than a builder and rejects a null tenant, and the JSON-RPC
 * transport needs protobuf-java pinned above what the Quarkus BOM supplies or
 * it fails with "Could not initialize class io.a2a.grpc.SendMessageRequest".
 * None of that is Beacon's problem, but all of it is why the pom carries an
 * explicit protobuf dependency.
 *
 * <p>Its echo is meant to FAIL the scenario. What matters is that the run
 * completes, stores an artifact, and reaches a verdict.
 */
@ApplicationScoped
public class ReferenceAgent {

    private static final String BASE = "http://127.0.0.1:8781";

    @Produces
    @PublicAgentCard
    public AgentCard agentCard() {
        return AgentCard.builder()
                .name("Beacon reference A2A agent (Java)")
                .description("Official a2a-java SDK agent used to check Beacon's A2A client.")
                .version("1.0.0")
                .supportedInterfaces(Collections.singletonList(
                        // A record in this release, not a builder, and the
                        // binding comes first: (protocolBinding, url, tenant,
                        // protocolVersion).
                        new AgentInterface(
                                TransportProtocol.JSONRPC.asString(),
                                BASE + "/",
                                "",
                                "1.0")))
                .capabilities(AgentCapabilities.builder().streaming(false).build())
                .defaultInputModes(Collections.singletonList("text"))
                .defaultOutputModes(Collections.singletonList("text"))
                .skills(Collections.singletonList(AgentSkill.builder()
                        .id("echo").name("echo").description("Echoes its input.")
                        .tags(List.of("test")).build()))
                .build();
    }

    @Produces
    public AgentExecutor agentExecutor() {
        return new AgentExecutor() {
            @Override
            public void execute(RequestContext context, AgentEmitter emitter) throws A2AError {
                emitter.sendMessage("REFERENCE-AGENT-JAVA-SAW: echo");
            }

            @Override
            public void cancel(RequestContext context, AgentEmitter emitter) throws A2AError {
                throw new UnsupportedOperationError();
            }
        };
    }
}
