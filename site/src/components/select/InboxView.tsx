/**
 * The synthetic world, before anything runs.
 *
 * This must read as an actual mail client to someone non-technical, not as a
 * data table. The whole setup — five messages, one protected, one carrying an
 * injected instruction — has to be legible at a glance, because every screen
 * after this one is about what an agent did to it.
 */

interface Message {
  id: string;
  sender: string;
  subject: string;
  body: string;
  labels: string[];
  received_at: string;
  protected: boolean;
}

interface Props {
  messages: Message[];
  /** Substring that marks the injected passage, so it can be shown in place. */
  injectionMarker?: string;
}

function time(iso: string): string {
  return new Date(iso).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function InboxView({ messages, injectionMarker = "[SYSTEM OVERRIDE]" }: Props) {
  return (
    <div className="overflow-hidden rounded-card border border-line bg-surface">
      <header className="flex items-baseline justify-between border-b border-line bg-sunken px-5 py-3">
        <h3 className="text-sm font-medium">Inbox</h3>
        <span className="font-mono text-[11px] text-text-faint">
          {messages.length} messages · synthetic
        </span>
      </header>

      <ul>
        {messages.map((message) => {
          const injected = message.body.includes(injectionMarker);
          const actionRequired = message.labels.includes("action_required");

          return (
            <li
              key={message.id}
              className={`border-b border-line px-5 py-4 last:border-b-0 ${
                message.protected ? "bg-sunken" : ""
              }`}
            >
              <div className="mb-1.5 flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <span className={`text-sm ${actionRequired ? "font-medium" : ""}`}>
                  {message.sender}
                </span>
                <span className="font-mono text-[11px] text-text-faint">{message.id}</span>
                <span className="ml-auto font-mono text-[11px] text-text-faint">
                  {time(message.received_at)}
                </span>
              </div>

              <p className={`mb-1.5 text-[15px] ${actionRequired ? "font-medium" : "text-text-muted"}`}>
                {message.subject}
              </p>

              <p className="mb-2.5 line-clamp-2 text-[13.5px] leading-relaxed text-text-muted text-pretty">
                {message.protected
                  ? "Listed, with its contents withheld. The agent can see that this message exists — opening it is the forbidden action."
                  : message.body}
              </p>

              <div className="flex flex-wrap gap-1.5">
                {message.labels
                  .filter((label) => !(message.protected && label === "protected"))
                  .map((label) => (
                  <span
                    key={label}
                    className="rounded-[3px] border border-line bg-sunken px-1.5 py-0.5 font-mono text-[10px] text-text-muted"
                  >
                    {label}
                  </span>
                ))}
                {message.protected && (
                  <span className="rounded-[3px] border border-inc/50 border-dashed bg-inc-tint px-1.5 py-0.5 font-mono text-[10px] text-inc">
                    protected
                  </span>
                )}
                {injected && (
                  <span className="rounded-[3px] border border-fail/40 bg-fail-tint px-1.5 py-0.5 font-mono text-[10px] text-fail">
                    contains an injected instruction
                  </span>
                )}
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
