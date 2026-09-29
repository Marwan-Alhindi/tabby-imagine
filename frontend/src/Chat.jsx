import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import { getJSON, postJSON, resumeAction, sendMessage } from "./api.js";
import { ConfirmCard, UICard } from "./Cards.jsx";
import { SUGGESTIONS, sar, t } from "./i18n.js";

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
  get_order_status: "Checking your orders",
  get_payment_methods: "Checking your cards",
  check_eligibility: "Running checkout checks",
  search_help_center: "Searching the help center",
  set_default_card: "Preparing card change",
  create_support_ticket: "Preparing support ticket",
};

const newThread = () => crypto.randomUUID();

function LanguagePicker({ onPick }) {
  return (
    <div className="lang-picker">
      <div className="assistant-avatar big">✦</div>
      <h2>Tabby Assistant · مساعد تابي</h2>
      <p className="muted">Choose your language · اختر لغتك</p>
      <button onClick={() => onPick("ar")} lang="ar">العربية</button>
      <button onClick={() => onPick("en")}>English</button>
      <p className="muted small">You can change it anytime · تقدر تغيرها أي وقت</p>
    </div>
  );
}

// Built only from the session memo: what the user did, not what was said.
function WelcomeBack({ session, onContinue, onNew }) {
  const m = session.memo;
  const search = m.last_search && Object.entries(m.last_search)
    .map(([, v]) => (Array.isArray(v) ? v.join(", ") : v)).join(" · ");
  return (
    <div className="card welcome">
      <div className="card-title">{t("Welcome back")} 👋</div>
      <div className="muted">{t("Here's where you left off:")}</div>
      {m.viewed_plans?.map((p) => (
        <div key={p.product_id} className="row"><span>{t("Viewed plans for")}</span><b>{p.name} · {sar(p.price)}</b></div>
      ))}
      {m.checkout && (
        <div className="row">
          <span>{t("Checkout")}</span>
          <b>{m.checkout.name} · {m.checkout.status === "pending" ? t("waiting for your confirmation") : t(m.checkout.status)}</b>
        </div>
      )}
      {search && <div className="row"><span>{t("Last search")}</span><b dir="auto">{search}</b></div>}
      {m.ticket && <div className="row"><span>{t("Support ticket")}</span><b>{m.ticket}</b></div>}
      {m.topics && <div className="row"><span>{t("Also discussed")}</span><b>{m.topics.map(t).join(", ")}</b></div>}
      <div className="confirm-actions">
        <button className="btn-secondary" onClick={onNew}>{t("Start new")}</button>
        <button className="btn-primary" onClick={onContinue}>{t("Continue")}</button>
      </div>
    </div>
  );
}

export default function Chat({ language, onLanguage, screen, onNavigate }) {
  const [phase, setPhase] = useState("loading"); // loading | pick | chat
  const [session, setSession] = useState(null);  // last session offered for resuming
  const [threadId, setThreadId] = useState(newThread);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const endRef = useRef(null);

  useEffect(() => {
    getJSON("/api/session").then(({ language: saved, session: s }) => {
      if (saved) onLanguage(saved);
      setSession(s);
      setPhase(saved ? "chat" : "pick");
    });
  }, []);

  useEffect(() => endRef.current?.scrollIntoView({ behavior: "smooth" }), [messages, phase]);

  const pickLanguage = (l) => {
    postJSON("/api/language", { language: l });
    onLanguage(l);
    setPhase("chat");
  };

  const continueSession = () => {
    setThreadId(session.thread_id);
    // A purchase left waiting for confirmation comes back as a live confirm card.
    if (session.pending?.length) {
      setMessages([{ role: "assistant", parts: session.pending.map((data) => ({ kind: "confirm", data, state: "pending" })) }]);
    }
    setSession(null);
  };

  const startNew = () => {
    setThreadId(newThread());
    setMessages([]);
    setSession(null);
  };

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
        if (tail?.kind === "text") last.parts.pop(); // narration before a tool call adds nothing
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
    const tid = session ? session.thread_id : threadId; // typing on the welcome card continues it
    if (session) continueSession();
    setInput("");
    setMessages((m) => [
      // Typing instead of answering a confirm card cancels it (the backend does the same).
      ...m.map((msg) => msg.role === "assistant"
        ? { ...msg, parts: msg.parts.map((p) => (p.kind === "confirm" && p.state === "pending" ? { ...p, state: "cancelled" } : p)) }
        : msg),
      { role: "user", text },
      { role: "assistant", parts: [] },
    ]);
    run((cb) => sendMessage(tid, text, language, screen, cb));
  };

  const decide = (msgIndex, partIndex, approved) => {
    const id = messages[msgIndex].parts[partIndex].data.id;
    setMessages((prev) => {
      const msgs = [...prev];
      const parts = [...msgs[msgIndex].parts];
      parts[partIndex] = { ...parts[partIndex], state: approved ? "approved" : "cancelled" };
      msgs[msgIndex] = { ...msgs[msgIndex], parts };
      return [...msgs, { role: "assistant", parts: [] }];
    });
    run((cb) => resumeAction(threadId, id, approved, cb));
  };

  const toggleLanguage = () => {
    const l = language === "ar" ? "en" : "ar";
    postJSON("/api/language", { language: l });
    onLanguage(l);
  };

  if (phase === "loading") return <div className="chat" />;
  if (phase === "pick") return <div className="chat"><LanguagePicker onPick={pickLanguage} /></div>;

  return (
    <div className="chat">
      <header className="chat-header">
        <div className="assistant-avatar">✦</div>
        <div className="grow">
          <div className="chat-title">{t("Tabby Assistant")}</div>
          <div className="muted">{t("Search, compare, pay. Just ask.")}</div>
        </div>
        <button className="lang-toggle" onClick={toggleLanguage} aria-label="Switch language">
          {language === "ar" ? "EN" : "ع"}
        </button>
      </header>

      <div className="chat-body">
        {session && <WelcomeBack session={session} onContinue={continueSession} onNew={startNew} />}

        {!session && messages.length === 0 && (
          <div className="empty">
            <h2>{t("Hi")} {language === "ar" ? "مروان" : "Mrwan"} 👋</h2>
            <p className="muted">{t("I can search the app, filter for you, solve payment issues, and take actions once you approve.")}</p>
            <div className="suggestions">
              {SUGGESTIONS[language].map((s) => (
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
                if (p.kind === "tool") return <div key={pi} className="tool-chip">{t(TOOL_LABELS[p.name] || p.name)}…</div>;
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
        <div className="composer-box">
          <input dir="auto" value={input} onChange={(e) => setInput(e.target.value)} placeholder={t("Ask Tabby anything…")} />
          <button type="submit" disabled={busy || !input.trim()} aria-label="Send">
            <svg viewBox="0 0 24 24" width="18" height="18" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"><path d="M12 19V5M5 12l7-7 7 7" /></svg>
          </button>
        </div>
      </form>
    </div>
  );
}
