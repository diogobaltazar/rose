import { useState, useEffect, useRef } from "react";
import { askAssistant } from "../api";
import type { ChatMessage } from "../api";
import { renderMarkdown } from "../utils/markdown";

const SYSTEM =
  "You are a helpful assistant for ALMA VICTORIA TOPGUN — an autonomous software development platform. " +
  "Answer questions about how to configure and use the platform. Be concise and precise. " +
  "Use the same technical vocabulary as the platform (missions, intel, pilots, sortie, logbook, sorties).";

interface Props {
  presetQuestion: string;
  componentTitle: string;
  token: string;
  onClose: () => void;
}

export default function ChatDialog({ presetQuestion, componentTitle, token, onClose }: Props) {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);

  const send = async (text: string) => {
    if (!text.trim() || loading) return;
    const next: ChatMessage[] = [...messages, { role: "user", content: text }];
    setMessages(next);
    setInput("");
    setLoading(true);
    setError(null);
    try {
      const response = await askAssistant(token, next, SYSTEM);
      setMessages([...next, { role: "assistant", content: response }]);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    send(presetQuestion);
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm p-4">
      <div className="relative w-full max-w-2xl bg-base border border-border-dim flex flex-col"
           style={{ maxHeight: "80vh" }}>

        {/* Header */}
        <div className="flex items-center justify-between px-5 py-3 border-b border-border-dim shrink-0">
          <div>
            <div className="font-mono text-xs text-amber-tac tracking-[0.3em] uppercase">AI ASSISTANT</div>
            <div className="font-mono text-xs text-text-muted mt-0.5">{componentTitle}</div>
          </div>
          <button onClick={onClose}
            className="font-mono text-xs text-text-muted hover:text-red-alert tracking-widest px-2 py-1">
            ✕ CLOSE
          </button>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 space-y-4 min-h-0">
          {messages.map((m, i) => (
            <div key={i} className={m.role === "user" ? "flex justify-end" : ""}>
              {m.role === "user" ? (
                <div className="max-w-[80%] bg-amber-tac/10 border border-amber-tac/30 px-4 py-2">
                  <p className="font-mono text-xs text-amber-tac whitespace-pre-wrap">{m.content}</p>
                </div>
              ) : (
                <div className="max-w-[95%]">
                  <div className="font-mono text-xs text-text-muted tracking-widest mb-1">TOPGUN AI</div>
                  <div className="space-y-0.5">
                    {renderMarkdown(m.content)}
                  </div>
                </div>
              )}
            </div>
          ))}

          {loading && (
            <div className="font-mono text-xs text-amber-tac animate-pulse_amber tracking-widest">
              THINKING…
            </div>
          )}

          {error && (
            <div className="font-mono text-xs text-red-alert border border-red-alert/30 px-3 py-2 space-y-1">
              <div>{error}</div>
              {error.toLowerCase().includes("unauthorized") && (
                <div className="text-text-muted">
                  Token may have expired — go to Settings → AI Provider → UPDATE to refresh it.
                </div>
              )}
            </div>
          )}

          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="border-t border-border-dim px-5 py-3 shrink-0">
          <div className="flex gap-2 items-end">
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder="Ask a follow-up… (Enter to send, Shift+Enter for newline)"
              rows={2}
              className="flex-1 bg-card border border-border-dim px-3 py-2 font-mono text-xs text-text-primary placeholder:text-text-muted focus:outline-none focus:border-amber-tac resize-none"
            />
            <button
              onClick={() => send(input)}
              disabled={!input.trim() || loading}
              className="font-mono text-xs px-4 py-2 border border-amber-tac text-amber-tac hover:bg-amber-tac/10 tracking-widest disabled:opacity-40 shrink-0"
            >
              SEND
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
