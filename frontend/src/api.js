// POST + read an SSE stream from the backend, calling onEvent(event, data) per message.
async function stream(path, body, onEvent) {
  const res = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += decoder.decode(value, { stream: true }).replace(/\r\n/g, "\n");
    let i;
    while ((i = buf.indexOf("\n\n")) >= 0) {
      const raw = buf.slice(0, i);
      buf = buf.slice(i + 2);
      let event = "message", data = "";
      for (const line of raw.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) onEvent(event, JSON.parse(data));
    }
  }
}

export const sendMessage = (thread_id, message, language, screen, onEvent) =>
  stream("/api/chat", { thread_id, message, language, screen }, onEvent);

export const resumeAction = (thread_id, interrupt_id, approved, onEvent) =>
  stream("/api/chat/resume", { thread_id, interrupt_id, approved }, onEvent);

export const getJSON = (path) => fetch(path).then((r) => r.json());

export const postJSON = (path, body) =>
  fetch(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }).then((r) => r.json());
