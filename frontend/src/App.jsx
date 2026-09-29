import { useEffect, useState } from "react";
import { getJSON } from "./api.js";
import { setLanguage, t } from "./i18n.js";
import { Payments, ProductCard } from "./Cards.jsx";
import Chat from "./Chat.jsx";

const Icon = {
  home: <path d="M4 11.5 12 4l8 7.5V20a1 1 0 0 1-1 1h-4.5v-6h-5v6H5a1 1 0 0 1-1-1z" />,
  shop: <path d="M6 8h12l-1 12H7zM9 8V6.5a3 3 0 0 1 6 0V8M9.5 12a2.5 2.5 0 0 0 5 0" />,
  payments: <path d="M12 3a9 9 0 1 0 9 9h-9zM14.5 3.3V9.5h6.2a9 9 0 0 0-6.2-6.2z" />,
  profile: <path d="M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8zm-7 8.5c0-3.3 3.1-5.5 7-5.5s7 2.2 7 5.5z" />,
  assistant: <path d="M12 2.5c.6 4.7 2.6 7 7.5 7.5v.1c-4.9.6-6.9 2.8-7.5 7.4h-.1c-.6-4.6-2.6-6.8-7.4-7.4V10c4.8-.5 6.8-2.8 7.5-7.5zM19 15.5c.3 2.1 1.1 3 3 3.2-1.9.3-2.7 1.1-3 3.3-.3-2.2-1.1-3-3-3.3 1.9-.2 2.7-1.1 3-3.2z" />,
};

const TABS = ["home", "shop", "payments", "profile", "assistant"];

function Placeholder({ title, note }) {
  return (
    <div className="screen">
      <h1>{title}</h1>
      <p className="muted">{note}</p>
    </div>
  );
}

function Shop({ nav }) {
  const [items, setItems] = useState([]);
  const params = new URLSearchParams();
  const all = { category: nav?.category, ...(nav?.filters || {}) };
  Object.entries(all).forEach(([k, v]) => {
    if (v == null || v === false) return;
    (Array.isArray(v) ? v : [v]).forEach((x) => params.append(k, x));
  });
  const qs = params.toString();
  useEffect(() => { getJSON(`/api/products?${qs}`).then(setItems); }, [qs]);
  return (
    <div className="screen">
      <h1>{t("Shop")}</h1>
      {qs && <div className="card-caption">Filtered by assistant: {decodeURIComponent(qs).replace(/&/g, " · ")}</div>}
      <div className="grid">{items.map((p) => <ProductCard key={p.id} p={p} />)}</div>
    </div>
  );
}

function PaymentsScreen() {
  const [data, setData] = useState(null);
  useEffect(() => { getJSON("/api/payments").then(setData); }, []);
  return (
    <div className="screen">
      <h1>{t("Payments")}</h1>
      {data && <Payments ui={data} />}
    </div>
  );
}

export default function App() {
  const [tab, setTab] = useState("assistant");
  const [language, setLang] = useState("en");
  setLanguage(language); // i18n reads it during this render
  const [fromTab, setFromTab] = useState("home"); // tab the user came from, sent as chat context
  const [shopNav, setShopNav] = useState(null);

  const go = (t) => {
    if (t === "assistant" && tab !== "assistant") setFromTab(tab);
    setTab(t);
  };
  const navigate = (ev) => {
    if (ev.screen === "shop") setShopNav(ev);
    setTab(ev.screen);
  };

  return (
    <div className="stage">
      <div className="phone" dir={language === "ar" ? "rtl" : "ltr"} lang={language}>
        <main className="content">
          {tab === "home" && <Placeholder title={t("Home")} note="Existing Tabby home screen." />}
          {tab === "shop" && <Shop nav={shopNav} />}
          {tab === "payments" && <PaymentsScreen />}
          {tab === "profile" && <Placeholder title={t("Profile")} note="Existing Tabby profile screen." />}
          {/* Chat stays mounted so the conversation survives tab switches. */}
          <div hidden={tab !== "assistant"} className="fill"><Chat language={language} onLanguage={setLang} screen={fromTab} onNavigate={navigate} /></div>
        </main>

        <nav className="tabbar">
          {TABS.map((t) => (
            <button key={t} className={`tab ${tab === t ? "active" : ""} ${t === "assistant" ? "tab-ai" : ""}`}
                    onClick={() => go(t)} aria-label={t}>
              <svg viewBox="0 0 24 24" width="26" height="26" fill={tab === t ? "currentColor" : "none"}
                   stroke="currentColor" strokeWidth="1.7" strokeLinejoin="round">{Icon[t]}</svg>
            </button>
          ))}
        </nav>
      </div>
    </div>
  );
}
