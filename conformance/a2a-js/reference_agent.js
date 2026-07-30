/**
 * A2A agent built with the official JavaScript SDK, to check Beacon against a
 * second independent implementation of the same specification.
 *
 *   cd conformance/a2a-js && npm install
 *   npm start        # 1.0 only, port 8751
 *   npm run start:v03  # legacy compatibility, port 8752
 *
 * Then, from the repository root:
 *
 *   python3 -m beacon a2a-inspect http://127.0.0.1:8751 --send hello
 *   python3 -m beacon run hosted-injection-resistance \
 *     --adapter a2a --agent-url http://127.0.0.1:8751
 *
 * The Python SDK found three wire-shape defects. This one found none of its
 * own, which is the useful result: the fixes generalise rather than being
 * specific to how one SDK serialises. What it did surface is stricter
 * behaviour — it validates the `A2A-Version` header, where every other server
 * tested ignores it. Beacon was sending a fixed "1.0" while choosing method
 * names from the card, so a 0.3 agent received a request claiming 1.0 and
 * calling `message/send`. This server answers that pair with an internal
 * error, which would have been recorded as the agent failing.
 *
 * Its trivial echo is meant to FAIL the scenario. What matters is that the
 * run completes, stores an artifact, and reaches a verdict.
 */

const express = require("express");
const { randomUUID } = require("crypto");
const { Role } = require("@a2a-js/sdk");
const { DefaultRequestHandler, InMemoryTaskStore } = require("@a2a-js/sdk/server");
const { agentCardHandler, jsonRpcHandler, UserBuilder } = require("@a2a-js/sdk/server/express");

const PORT = Number(process.argv[2]) || 8751;
const COMPAT = process.argv.includes("--v03");

const card = {
  name: "Beacon reference A2A agent (JS)",
  description: "Official @a2a-js/sdk agent used to check Beacon's A2A client.",
  version: "1.0.0",
  protocolVersion: "1.0",
  supportedInterfaces: [
    { url: `http://127.0.0.1:${PORT}/`, protocolBinding: "JSONRPC", protocolVersion: "1.0" },
  ],
  capabilities: { streaming: false },
  defaultInputModes: ["text/plain"],
  defaultOutputModes: ["text/plain"],
  skills: [{ id: "echo", name: "echo", description: "Echoes its input.", tags: ["test"] }],
};

const executor = {
  async execute(requestContext, eventBus) {
    const parts = requestContext.userMessage?.parts ?? [];
    const text = parts
      .map((p) => p.content?.value ?? p.text ?? "")
      .join("");
    eventBus.publish({
      kind: "message",
      data: {
        messageId: randomUUID(),
        role: Role.ROLE_AGENT,  // numeric enum; a string serialises to UNRECOGNIZED
        parts: [
          { content: { $case: "text", value: `REFERENCE-AGENT-JS-SAW: ${text.slice(0, 200)}` } },
        ],
      },
    });
    eventBus.finished();
  },
  async cancelTask() {
    throw new Error("nothing to cancel");
  },
};

const handler = new DefaultRequestHandler(card, new InMemoryTaskStore(), executor);
const app = express();
app.use(express.json());
// Both routers serve at their own "/", so they are mounted where the
// specification says they live.
app.use("/.well-known/agent-card.json",
  agentCardHandler({ agentCardProvider: handler, legacyCompat: { enabled: COMPAT } }));
app.use("/", jsonRpcHandler({
  requestHandler: handler,
  userBuilder: UserBuilder.noAuthentication,
  legacyCompat: { enabled: COMPAT },
}));
app.listen(PORT, "127.0.0.1", () =>
  console.log(`JS reference agent on http://127.0.0.1:${PORT} (${COMPAT ? "1.0 + 0.3" : "1.0 only"})`)
);
