import { useEffect, useRef, useState } from "react";
import { useLocation, useSearchParams } from "react-router-dom";
import { aiApi, approvalsApi, type AICommandResponse, type AIAction } from "../api/client";
import { useMutation } from "../lib/hooks";
import { PageHeader, FormAlert } from "../components/Page";
import AIRecommendationCard from "../components/AIRecommendationCard";
import StatusPill from "../components/StatusPill";
import EmptyState from "../components/EmptyState";

interface Message {
  id: number;
  role: "user" | "ai" | "error";
  text: string;
  response?: AICommandResponse;
}

let msgId = 0;

export default function AICommand() {
  const location = useLocation();
  const [params] = useSearchParams();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [scanState, setScanState] = useState<"idle" | "busy" | "done" | "error">("idle");
  const bottomRef = useRef<HTMLDivElement>(null);

  const ask = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setBusy(true);
    setMessages((m) => [...m, { id: ++msgId, role: "user", text: q }]);
    setInput("");
    try {
      const res = await aiApi.command(q);
      setMessages((m) => [...m, { id: ++msgId, role: "ai", text: res.answer, response: res }]);
    } catch (e) {
      setMessages((m) => [...m, { id: ++msgId, role: "error", text: e instanceof Error ? e.message : "AI request failed" }]);
    } finally {
      setBusy(false);
    }
  };

  useEffect(() => {
    const prefill = (location.state as { message?: string } | null)?.message;
    if (prefill) ask(prefill);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (params.get("scan") === "1" && scanState === "idle") {
      setScanState("busy");
      aiApi
        .scanExceptions()
        .then((r) => {
          setMessages((m) => [
            ...m,
            { id: ++msgId, role: "ai", text: `Exception scan complete — ${r.created.length} new exception${r.created.length === 1 ? "" : "s"} created.` },
          ]);
          setScanState("done");
        })
        .catch(() => setScanState("error"));
    }
  }, [params, scanState]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  return (
    <div>
      <PageHeader
        title="AI Command"
        sub="Ask anything — answers, data, recommendations, actions"
        actions={
          <button className="btn btn-ghost" disabled={scanState === "busy"} onClick={() => window.location.href = "/ai?scan=1"}>
            {scanState === "busy" ? "Scanning…" : "⚠ Run exception scan"}
          </button>
        }
      />
      <div className="chat">
        <div className="chat-log">
          {messages.length === 0 && (
            <EmptyState
              title="Ask the AI"
              hint="Try: “Which loads are at risk of late delivery?” or “Find carriers for the Chicago lane”"
            />
          )}
          {messages.map((m) => (
            <div key={m.id} className={`chat-msg ${m.role}`}>
              {m.role === "user" ? (
                <div className="chat-bubble user">{m.text}</div>
              ) : m.role === "error" ? (
                <div className="chat-bubble error">{m.text}</div>
              ) : (
                <div className="chat-bubble ai">
                  <div className="chat-answer">{m.text}</div>
                  {m.response && <AIResponseBody res={m.response} />}
                </div>
              )}
            </div>
          ))}
          {busy && <div className="chat-msg ai"><div className="chat-bubble ai typing">Thinking…</div></div>}
          <div ref={bottomRef} />
        </div>
        <form
          className="chat-input-row"
          onSubmit={(e) => { e.preventDefault(); ask(input); }}
        >
          <input
            className="input"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Ask about loads, carriers, rates, exceptions…"
            disabled={busy}
          />
          <button className="btn btn-primary" type="submit" disabled={busy || !input.trim()}>
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

function AIResponseBody({ res }: { res: AICommandResponse }) {
  const [actionState, setActionState] = useState<Record<string, string>>({});
  const approve = useMutation((id: string) => approvalsApi.approve(id));
  const reject = useMutation((args: { id: string; reason?: string }) => approvalsApi.reject(args.id, args.reason));

  const execAction = async (a: AIAction) => {
    setActionState((s) => ({ ...s, [a.label]: "working" }));
    try {
      const r = await aiApi.proposeAction({
        agent: "ops_analyst_agent",
        action_type: a.type,
        payload: a.payload,
      });
      setActionState((s) => ({
        ...s,
        [a.label]: r.decision === "auto" ? "executed" : r.decision === "require_approval" ? `awaiting approval${r.approval_id ? ` (${r.approval_id.slice(0, 8)})` : ""}` : r.decision,
      }));
    } catch (e) {
      setActionState((s) => ({ ...s, [a.label]: `failed: ${e instanceof Error ? e.message : "error"}` }));
    }
  };

  return (
    <div className="ai-resp">
      <div className="ai-meta">
        <span className="muted small">confidence {Math.round(res.confidence * 100)}%</span>
        {res.approval_required && <StatusPill status="pending" />}
      </div>
      {res.recommendations.length > 0 && (
        <div className="ai-recs">
          {res.recommendations.map((rec, i) => (
            <AIRecommendationCard key={i} rec={rec} />
          ))}
        </div>
      )}
      {res.actions.length > 0 && (
        <div className="ai-actions">
          <h4>Suggested actions</h4>
          {res.actions.map((a, i) => (
            <div key={i} className="ai-action-row">
              <span>{a.label}</span>
              <button className="btn btn-ghost btn-sm" disabled={actionState[a.label] === "working"} onClick={() => execAction(a)}>
                {actionState[a.label] === "working" ? "Working…" : actionState[a.label] || "Execute"}
              </button>
            </div>
          ))}
          <FormAlert error={approve.error || reject.error} />
        </div>
      )}
      {res.data && Object.keys(res.data).length > 0 && (
        <details className="ai-data">
          <summary>Raw data</summary>
          <pre>{JSON.stringify(res.data, null, 2)}</pre>
        </details>
      )}
    </div>
  );
}
