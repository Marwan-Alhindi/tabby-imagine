import { useEffect, useRef, useState } from "react";
import Markdown from "react-markdown";
import { getJSON, postJSON, resumeAction, sendMessage } from "./api.js";
import { ConfirmCard, UICard } from "./Cards.jsx";
import { SUGGESTIONS, lang, sar, t } from "./i18n.js";

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

// "Mobiles · Apple, Samsung · 256GB+ · up to 11,111 SAR" instead of raw filter values.
function formatSearch(s) {
  if (!s) return null;
  const parts = [
    s.query && `“${s.query}”`,
    s.category && t(`cat:${s.category}`),
    s.brands?.join(", "),
    s.min_storage_gb && `${s.min_storage_gb}GB+`,
    s.color,
    s.store,
    s.min_price && `${t("from")} ${sar(s.min_price)}`,
    s.max_price && `${t("up to")} ${sar(s.max_price)}`,
    s.deals_only && t("Deals"),
  ].filter(Boolean);
  return parts.length ? parts.join(" · ") : null;
}

// Built only from the session memo: what the user did, not what was said.
function SessionSummary({ memo: m }) {
  const search = formatSearch(m.last_search);
  return (
    <>
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
    </>
  );
}

function WelcomeBack({ session, onContinue, onNew }) {
  return (
    <div className="card welcome">
      <div className="card-title">{t("Welcome back")} 👋</div>
      <div className="muted">{t("Here's where you left off:")}</div>
      <SessionSummary memo={session.memo} />
      <div className="confirm-actions">
        <button className="btn-secondary" onClick={onNew}>{t("Start new")}</button>
        <button className="btn-primary" onClick={() => onContinue(session)}>{t("Continue")}</button>
      </div>
    </div>
  );
}

const when = (iso) => new Date(iso).toLocaleString(lang() === "ar" ? "ar-SA" : "en-US",
  { weekday: "short", hour: "numeric", minute: "2-digit" });

function HistorySheet({ current, onPick, onNew, onClose }) {
  const [sessions, setSessions] = useState(null);
  useEffect(() => { getJSON("/api/sessions").then(setSessions); }, []);
  return (
    <div className="sheet-backdrop" onClick={onClose}>
      <div className="sheet" onClick={(e) => e.stopPropagation()}>
        <div className="sheet-head">
          <div className="card-title">{t("Recent")}</div>
          <button className="chip-btn" onClick={onNew}>+ {t("Start new")}</button>
        </div>
        <p className="muted small">{t("Summaries of your last 7 days. Conversations themselves aren't shown.")}</p>
        {sessions === null && <div className="typing"><i /><i /><i /></div>}
        {sessions?.length === 0 && <div className="muted">{t("No recent sessions")}</div>}
        {sessions?.map((s) => (
          <div key={s.thread_id} className="card session-item">
            <div className="sheet-head">
              <span className="muted">{when(s.updated_at)}</span>
              {s.thread_id === current
                ? <span className="filter-tag">{t("Current")}</span>
                : <button className="chip-btn" onClick={() => onPick(s)}>{t("Continue")}</button>}
            </div>
            <SessionSummary memo={s.memo} />
          </div>
        ))}
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
  const [showHistory, setShowHistory] = useState(false);
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

  // Resume a past session: show its summary (not its transcript) and any purchase
  // still waiting for confirmation as a live confirm card.
  const continueSession = (s) => {
    setThreadId(s.thread_id);
    setMessages([{ role: "assistant", parts: [
      { kind: "resumed", memo: s.memo },
      ...(s.pending || []).map((data) => ({ kind: "confirm", data, state: "pending" })),
    ] }]);
    setSession(null);
    setShowHistory(false);
  };

  const startNew = () => {
    setThreadId(newThread());
    setMessages([]);
    setSession(null);
    setShowHistory(false);
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
      } else if (event === "ui" && data.type === "model_fallback") {
        if (!last.parts.some((p) => p.ui?.type === "model_fallback")) last.parts.push({ kind: "ui", ui: data });
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
    if (session) continueSession(session);
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
        <button className="lang-toggle" onClick={() => setShowHistory(true)} aria-label={t("Recent")}>
          <svg viewBox="0 0 24 24" width="20" height="20" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
            <path d="M3 12a9 9 0 1 0 3-6.7L3 8M3 3v5h5M12 7v5l3 2" />
          </svg>
        </button>
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
                if (p.kind === "resumed") return (
                  <div key={pi} className="card resumed">
                    <div className="card-sub">{t("Continuing where you left off")}</div>
                    <SessionSummary memo={p.memo} />
                  </div>
                );
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

      {showHistory && (
        <HistorySheet current={threadId} onPick={continueSession} onNew={startNew} onClose={() => setShowHistory(false)} />
      )}

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
