// Renders the structured `ui` events the assistant's tools emit.

const EMOJI = { mobiles: "📱", electronics: "💻", travel: "✈️", spa_salon: "💆", fashion: "👜", beauty: "🧴" };
const sar = (n) => `${Number(n).toLocaleString("en-US", { maximumFractionDigits: 2 })} SAR`;

export function ProductCard({ p, onAsk }) {
  const off = p.original_price ? Math.round((1 - p.price / p.original_price) * 100) : 0;
  return (
    <div className="product">
      <div className="product-img">
        <span>{EMOJI[p.category] || "🛍️"}</span>
        {off > 0 && <em className="badge">-{off}%</em>}
      </div>
      <div className="product-name">{p.name}</div>
      <div className="product-store">{p.store_name} · ★ {p.rating}</div>
      <div className="product-price">
        {sar(p.price)} {p.original_price && <s>{Number(p.original_price).toLocaleString()}</s>}
      </div>
      {p.monthly_from && <div className="product-monthly">from {sar(p.monthly_from)}/mo with tabby</div>}
      {onAsk && (
        <button className="chip-btn" onClick={() => onAsk(`I want the ${p.name} (id ${p.id}). What are my plan options?`)}>
          Plans
        </button>
      )}
    </div>
  );
}

function Products({ ui, onAsk }) {
  if (!ui.items.length) return <div className="card muted">No matching products.</div>;
  return (
    <div>
      <div className="card-caption">
        {ui.total} result{ui.total === 1 ? "" : "s"}
        {Object.entries(ui.filters || {}).filter(([, v]) => v != null).map(([k, v]) => (
          <span key={k} className="filter-tag">{k.replace(/_/g, " ")}: {Array.isArray(v) ? v.join(", ") : String(v)}</span>
        ))}
      </div>
      <div className="h-scroll">{ui.items.map((p) => <ProductCard key={p.id} p={p} onAsk={onAsk} />)}</div>
    </div>
  );
}

function Comparison({ ui }) {
  const keys = [...new Set(ui.items.flatMap((p) => Object.keys(p.specs)))];
  return (
    <div className="card table-wrap">
      <table>
        <thead><tr><th></th>{ui.items.map((p) => <th key={p.id}>{p.name}</th>)}</tr></thead>
        <tbody>
          <tr><td>Price</td>{ui.items.map((p) => <td key={p.id}><b>{sar(p.price)}</b></td>)}</tr>
          <tr><td>Monthly from</td>{ui.items.map((p) => <td key={p.id}>{p.monthly_from ? sar(p.monthly_from) : "-"}</td>)}</tr>
          <tr><td>Store</td>{ui.items.map((p) => <td key={p.id}>{p.store_name}</td>)}</tr>
          <tr><td>Rating</td>{ui.items.map((p) => <td key={p.id}>★ {p.rating}</td>)}</tr>
          {keys.map((k) => (
            <tr key={k}><td>{k.replace(/_/g, " ")}</td>{ui.items.map((p) => <td key={p.id}>{p.specs[k] ?? "-"}</td>)}</tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Plans({ ui }) {
  return (
    <div className="card">
      <div className="card-title">{ui.product || "Plans"} · {sar(ui.price)}</div>
      {ui.options.length === 0 && <div className="muted">No tabby plan for this amount.</div>}
      {ui.options.map((o) => (
        <div key={o.plan} className="row">
          <div>
            <div className="row-main">{o.label}</div>
            <div className="muted">{o.fee_pct ? `${o.fee_pct}% fee` : "No interest, no fees"}</div>
          </div>
          <div className="row-amount">{o.installments} × {sar(o.per_installment)}</div>
        </div>
      ))}
    </div>
  );
}

export function Payments({ ui }) {
  return (
    <div className="card">
      <div className="muted">Due in 30 days</div>
      <div className="big-amount">{sar(ui.due_in_30_days)}</div>
      <div className="muted">Total due {sar(ui.total_outstanding)} · Available {sar(ui.available_limit)}</div>
      {ui.upcoming.map((i) => (
        <div key={i.id} className="row">
          <div>
            <div className="row-main">{i.product}</div>
            <div className="muted">{i.store} · due {i.due}</div>
          </div>
          <div className="row-amount">{sar(i.amount)}</div>
        </div>
      ))}
    </div>
  );
}

function Account({ ui }) {
  return (
    <div className="card">
      <div className="row"><span>Cashback balance</span><b>{sar(ui.cashback_balance)}</b></div>
      <div className="row"><span>Profile completion</span><b>{ui.profile_completion_pct}%</b></div>
      <div className="row"><span>Referral reward</span><b>up to {sar(ui.referral.max_reward)}</b></div>
      {ui.todo.length > 0 && <div className="muted">To do: {ui.todo.join(", ")}</div>}
    </div>
  );
}

function Stores({ ui }) {
  return (
    <div className="h-scroll">
      {ui.items.map((s) => (
        <div key={s.id} className="store">
          <div className="store-logo">{s.name[0]}</div>
          <div className="store-name">{s.name}</div>
          {s.cashback_pct > 0 && <div className="muted">{s.cashback_pct}% cashback</div>}
        </div>
      ))}
    </div>
  );
}

function Referral({ ui }) {
  return (
    <div className="card">
      <div className="card-title">Invite friends, earn up to {sar(ui.max_reward)}</div>
      <div className="link-box">{ui.link}</div>
      <button className="chip-btn" onClick={() => navigator.clipboard?.writeText(ui.link)}>Copy link</button>
    </div>
  );
}

function Receipt({ ui }) {
  return (
    <div className="card receipt">
      <div className="card-title">✓ {ui.title}</div>
      {ui.order && <div className="muted">{ui.order.product} · {ui.order.store} · {sar(ui.order.total)}</div>}
      {ui.address && <div className="muted">{ui.address.street}, {ui.address.district}, {ui.address.city}</div>}
    </div>
  );
}

export function UICard({ ui, onAsk }) {
  switch (ui.type) {
    case "products": return <Products ui={ui} onAsk={onAsk} />;
    case "comparison": return <Comparison ui={ui} />;
    case "plans": return <Plans ui={ui} />;
    case "payments": return <Payments ui={ui} />;
    case "account": return <Account ui={ui} />;
    case "stores": return <Stores ui={ui} />;
    case "referral": return <Referral ui={ui} />;
    case "receipt": return <Receipt ui={ui} />;
    case "navigate": return <div className="tool-chip">↗ Opened {ui.screen}{ui.category ? ` · ${ui.category}` : ""}</div>;
    default: return null;
  }
}

export function ConfirmCard({ part, onDecide }) {
  const { data, state } = part;
  return (
    <div className={`card confirm ${state}`}>
      <div className="confirm-head">Needs your approval</div>
      <div className="card-title">{data.title}</div>
      {data.lines.map(([k, v]) => (
        <div key={k} className="row"><span className="muted">{k}</span><span>{v}</span></div>
      ))}
      {state === "pending" ? (
        <div className="confirm-actions">
          <button className="btn-secondary" onClick={() => onDecide(false)}>Cancel</button>
          <button className="btn-primary" onClick={() => onDecide(true)}>{data.confirm_label}</button>
        </div>
      ) : (
        <div className="muted">{state === "approved" ? "Approved" : "Cancelled"}</div>
      )}
    </div>
  );
}
