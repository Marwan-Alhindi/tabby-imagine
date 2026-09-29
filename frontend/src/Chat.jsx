import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import { resumeAction, sendMessage } from "./api.js";
import { ConfirmCard, UICard } from "./Cards.jsx";

const TOOL_LABELS = {
  search_products: "Searching products",
  get_deals: "Finding deals",
  search_stores: "Looking up stores",
  compare_products: "Comparing",
  get_payment_plans: "Calculating plans",
  get_payments: "Checking your payments",
  get_account: "Checking your account",
  open_screen: "Opening screen",
  share_referral: "Getting your invite link",
  start_checkout: "Preparing checkout",
  pay_installment: "Preparing payment",
  update_home_address: "Preparing address",
};

const SUGGESTIONS = [
  "ابي ايفون او سامسونج ٢٥٦ جيجا وقسطه الشهري اقل من ١٠٠٠",
  "Best deals on electronics right now",
  "What do I owe this month?",
  "Compare the iPhone 17 Pro and Galaxy S25 Ultra",
  "Spa offers with the most cashback",
];

const threadId = crypto.randomUUID();

export default function Chat({ screen, onNavigate }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [messages]);

  // Apply one streamed event to the last (assistant) message.
  const apply = (event, data) =>
    setMessages((prev) => {
      const msgs = [...prev];
      const last = { ...msgs[msgs.length - 1], parts: [...msgs[msgs.length - 1].parts] };
      msgs[msgs.length - 1] = last;
      const tail = last.parts[last.parts.length - 1];
      if (event === "token") {
        if (tail?.kind === "text") last.parts[last.parts.length - 1] = { ...tail, text: tail.text + data.text };
        else last.parts.push({ kind: "text", text: data.text });
      } else if (event === "tool") {
        last.parts.push({ kind: "tool", name: data.name });
      } else if (event === "ui") {
        last.parts.push({ kind: "ui", ui: data });
        if (data.type === "navigate") onNavigate(data);
      } else if (event === "confirm") {
        last.parts.push({ kind: "confirm", data, state: "pending" });
      } else if (event === "error") {
        last.parts.push({ kind: "text", text: `⚠️ ${data.message}` });
      }
      return msgs;
    });

  const run = async (fn) => {
    setBusy(true);
    try {
      await fn(apply);
    } catch (e) {
      apply("error", { message: e.message });
    } finally {
      setBusy(false);
    }
  };

  const send = (text) => {
    if (!text.trim() || busy) return;
    setInput("");
    setMessages((m) => [...m, { role: "user", text }, { role: "assistant", parts: [] }]);
    run((cb) => sendMessage(threadId, text, screen, cb));
  };

  const decide = (msgIndex, partIndex, approved) => {
    setMessages((prev) => {
      const msgs = [...prev];
      const parts = [...msgs[msgIndex].parts];
      parts[partIndex] = { ...parts[partIndex], state: approved ? "approved" : "cancelled" };
      msgs[msgIndex] = { ...msgs[msgIndex], parts };
      return [...msgs, { role: "assistant", parts: [] }];
    });
    const id = messages[msgIndex].parts[partIndex].data.id;
    run((cb) => resumeAction(threadId, id, approved, cb));
  };

  return (
    <div className="chat">
      <header className="chat-header">
        <div className="assistant-avatar">✦</div>
        <div>
          <div className="chat-title">Tabby Assistant</div>
          <div className="muted">Search, compare, pay. Just ask.</div>
        </div>
      </header>

      <div className="chat-body">
        {messages.length === 0 && (
          <div className="empty">
            <h2>Hi Mrwan 👋</h2>
            <p className="muted">Ask in Arabic or English. I can search the app, filter for you, and take actions once you approve.</p>
            <div className="suggestions">
              {SUGGESTIONS.map((s) => (
                <button key={s} dir="auto" onClick={() => send(s)}>{s}</button>
              ))}
            </div>
          </div>
        )}

        {messages.map((m, mi) =>
          m.role === "user" ? (
            <div key={mi} className="bubble user" dir="auto">{m.text}</div>
          ) : (
            <div key={mi} className="assistant-turn">
              {m.parts.map((p, pi) => {
                if (p.kind === "text") return <div key={pi} className="bubble assistant" dir="auto"><Markdown>{p.text}</Markdown></div>;
                if (p.kind === "tool") return <div key={pi} className="tool-chip">{TOOL_LABELS[p.name] || p.name}…</div>;
                if (p.kind === "ui") return <UICard key={pi} ui={p.ui} onAsk={send} />;
                if (p.kind === "confirm") return <ConfirmCard key={pi} part={p} onDecide={(ok) => decide(mi, pi, ok)} />;
                return null;
              })}
              {busy && mi === messages.length - 1 && <div className="typing"><i /><i /><i /></div>}
            </div>
          )
        )}
        <div ref={endRef} />
      </div>

      <form className="composer" onSubmit={(e) => { e.preventDefault(); send(input); }}>
        <input dir="auto" value={input} onChange={(e) => setInput(e.target.value)} placeholder="Ask Tabby anything… اسأل تابي" />
        <button type="submit" disabled={busy || !input.trim()} aria-label="Send">↑</button>
      </form>
    </div>
  );
}
