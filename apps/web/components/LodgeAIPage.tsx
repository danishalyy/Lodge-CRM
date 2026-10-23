"use client";
import { useEffect, useRef, useState } from "react";
import { aiApi, getActiveLodgeId, getActiveUserId } from "@/lib/api";
import { aiCopy as copy } from "@/lib/strings/ai";
import { formatDateTime } from "@/lib/formatting";
import { Field } from "./ui/field";
import { Form } from "./ui/form";
export default function LodgeAIPage() {
  const [status, setStatus] = useState<any>(null),
    [conversations, setConversations] = useState<any[]>([]),
    [conversation, setConversation] = useState(""),
    [messages, setMessages] = useState<any[]>([]),
    [question, setQuestion] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const scope = () => `${getActiveUserId()}:${getActiveLodgeId()}`;
  async function load() {
    const token = ++generation.current,
      origin = scope();
    setStatus(null);
    setError("");
    try {
      const [s, c] = await Promise.all([aiApi.status(), aiApi.conversations()]);
      if (token !== generation.current || origin !== scope()) return;
      setStatus(s);
      setConversations(c);
    } catch (e) {
      if (token === generation.current && origin === scope())
        setError((e as Error).message);
    }
  }
  useEffect(() => {
    void load();
    const change = () => {
      setConversation("");
      setMessages([]);
      setQuestion("");
      setBusy(false);
      void load();
    };
    window.addEventListener("safarios-lodge-changed", change);
    return () => {
      generation.current++;
      window.removeEventListener("safarios-lodge-changed", change);
    };
  }, []);
  async function open(id: string) {
    const origin = scope(),
      token = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const rows = await aiApi.messages(id);
      if (token === generation.current && origin === scope()) {
        setConversation(id);
        setMessages(rows);
      }
    } catch (e) {
      if (token === generation.current && origin === scope())
        setError((e as Error).message || copy.historyFailed);
    } finally {
      if (token === generation.current && origin === scope()) setBusy(false);
    }
  }
  async function send(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy || !question.trim()) return;
    const origin = scope(),
      token = ++generation.current;
    setBusy(true);
    setError("");
    try {
      let id = conversation;
      if (!id) {
        const created = await aiApi.create();
        if (token !== generation.current || origin !== scope()) return;
        id = created.id;
        setConversation(id);
        setConversations((old) => [created, ...old]);
      }
      const answer = await aiApi.send(id, question.trim());
      if (token !== generation.current || origin !== scope()) return;
      if (!answer.content) throw Error(copy.emptyReply);
      const rows = await aiApi.messages(id);
      if (token === generation.current && origin === scope()) {
        setMessages(rows);
        setQuestion("");
      }
    } catch (e) {
      if (token === generation.current && origin === scope())
        setError((e as Error).message || copy.failed);
    } finally {
      if (token === generation.current && origin === scope()) setBusy(false);
    }
  }
  const ready = status?.state === "ready" && status.tools?.length > 0;
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">{copy.eyebrow}</span>
          <h1>{copy.title}</h1>
          <p>{copy.intro}</p>
          {status?.scope && (
            <p>
              {copy.scope}: <strong>{status.scope.lodge_name}</strong>
            </p>
          )}
        </div>
      </div>
      {error && (
        <p className="dangerText" role="alert">
          {error}{" "}
          <button className="button secondary" onClick={load} disabled={busy}>
            {copy.retry}
          </button>
        </p>
      )}
      {!status && !error && (
        <section className="panel" role="status">
          {copy.loading}
        </section>
      )}
      {status && !ready && (
        <section className="panel statePanel">
          <h2>
            {status.state === "test_only" ? copy.testOnly : copy.unavailable}
          </h2>
          <p>
            {status.state === "test_only"
              ? copy.testOnlyBody
              : copy.unavailableBody}
          </p>
          <button className="button" onClick={load}>
            {copy.retry}
          </button>
        </section>
      )}
      {ready && (
        <div className="aiWorkspace">
          <aside className="panel">
            <h2>{copy.conversations}</h2>
            <button
              className="button"
              disabled={busy}
              onClick={() => {
                setConversation("");
                setMessages([]);
                setError("");
              }}
            >
              {copy.newConversation}
            </button>
            {!conversations.length && <p>{copy.noHistory}</p>}
            <nav aria-label={copy.conversations}>
              {conversations.map((c) => (
                <button
                  className="button secondary"
                  key={c.id}
                  aria-current={conversation === c.id ? "true" : undefined}
                  disabled={busy}
                  onClick={() => open(c.id)}
                >
                  {formatDateTime(c.created_at)}
                </button>
              ))}
            </nav>
          </aside>
          <section className="panel aiConversation" aria-busy={busy}>
            {!messages.length && <p>{copy.empty}</p>}
            {!messages.length && (
              <div className="aiSuggestions" aria-label={copy.suggestion}>
                {status.tools
                  .filter((t: any) => t.suggestion)
                  .map((t: any) => (
                    <button
                      className="button secondary"
                      disabled={busy}
                      key={t.name}
                      onClick={() => setQuestion(t.suggestion)}
                    >
                      {t.suggestion}
                    </button>
                  ))}
              </div>
            )}
            <div className="aiMessages" aria-live="polite">
              {messages.map((m) => (
                <article className="aiMessage" key={m.id}>
                  <h2>{m.role === "user" ? copy.you : copy.assistant}</h2>
                  <p>{m.content}</p>
                  {m.role === "assistant" && (
                    <details>
                      <summary>{copy.sources}</summary>
                      {m.sources?.length ? (
                        <ul>
                          {m.sources.map((s: any, i: number) => (
                            <li key={i}>
                              {s.label || copy.live} ·{" "}
                              {formatDateTime(s.retrieved_at)}
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p>{copy.noSources}</p>
                      )}
                    </details>
                  )}
                </article>
              ))}
            </div>
            {busy && <p role="status">{copy.busy}</p>}
            <Form onSubmit={send}>
              <Field label={copy.question}>
                <textarea
                  name="content"
                  required
                  maxLength={3000}
                  rows={3}
                  value={question}
                  onChange={(e) => setQuestion(e.target.value)}
                  disabled={busy}
                />
              </Field>
              <button
                className="button primary"
                disabled={busy || !question.trim()}
              >
                {copy.send}
              </button>
            </Form>
          </section>
        </div>
      )}
    </>
  );
}
