"use client";
import { useEffect, useRef, useState } from "react";
import { ApiError, aiApi, getActiveLodgeId, getActiveUserId } from "@/lib/api";
import { aiCopy as copy } from "@/lib/strings/ai";
import { formatDate, formatDateTime } from "@/lib/formatting";
import { Field } from "./ui/field";
import { Form } from "./ui/form";
import KnowledgeLibrary from "./KnowledgeLibrary";
import { knowledgeCopy } from "@/lib/strings/knowledge";
import { readableLabel } from "@/lib/strings/content";
export default function LodgeAIPage({
  scopeType = "lodge",
}: {
  scopeType?: "lodge" | "group";
}) {
  const [status, setStatus] = useState<any>(null),
    [conversations, setConversations] = useState<any[]>([]),
    [conversation, setConversation] = useState(""),
    [messages, setMessages] = useState<any[]>([]),
    [question, setQuestion] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const generation = useRef(0);
  const scope = () => `${getActiveUserId()}:${getActiveLodgeId()}:${scopeType}`;
  async function load() {
    const token = ++generation.current,
      origin = scope();
    setStatus(null);
    setError("");
    try {
      const [s, c] = await Promise.all([
        aiApi.status(scopeType),
        aiApi.conversations(scopeType),
      ]);
      if (token !== generation.current || origin !== scope()) return;
      setStatus(s);
      setConversations(c);
      if (conversation && !c.some((row: any) => row.id === conversation)) {
        setConversation("");
        setMessages([]);
      }
    } catch (e) {
      if (token === generation.current && origin === scope()) {
        if (e instanceof ApiError && [401, 403, 409].includes(e.status)) {
          setConversation("");
          setMessages([]);
          setStatus(null);
        }
        setError((e as Error).message);
      }
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
  }, [scopeType]);
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
      if (token === generation.current && origin === scope()) {
        if (e instanceof ApiError && [401, 403, 409].includes(e.status)) {
          setConversation("");
          setMessages([]);
          setStatus(null);
        }
        setError((e as Error).message || copy.historyFailed);
      }
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
        const created = await aiApi.create(scopeType);
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
      if (token === generation.current && origin === scope()) {
        if (e instanceof ApiError && [401, 403, 409].includes(e.status)) {
          setConversation("");
          setMessages([]);
          setStatus(null);
        }
        setError((e as Error).message || copy.failed);
      }
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
          <h1>{scopeType === "group" ? copy.groupTitle : copy.title}</h1>
          <p>{scopeType === "group" ? copy.groupIntro : copy.intro}</p>
          {status?.scope && scopeType !== "group" && (
            <p>
              {copy.scope}: <strong>{status.scope.lodge_name}</strong>
            </p>
          )}
        </div>
      </div>
      {status?.scope?.type === "group" && (
        <section className="panel groupAiCoverage">
          <h2>
            {copy.groupScope}: {status.scope.group_name}
          </h2>
          <p>
            {copy.includedLodges}:{" "}
            {status.scope.lodges.map((l: any) => l.lodge_name).join(", ")}
          </p>
          {status.scope.excluded_count > 0 && (
            <p>{copy.excludedLodges(status.scope.excluded_count)}</p>
          )}
          <p>{copy.groupCoverage}</p>
        </section>
      )}
      {status?.knowledge_enabled && scopeType === "lodge" && (
        <KnowledgeLibrary />
      )}
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
                  .slice(0, 5)
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
                              {s.partial && <span> · {copy.partial}</span>}
                              {s.kind === "group" && (
                                <>
                                  <p>
                                    {copy.groupScope}: {s.group_name}
                                  </p>
                                  {s.excluded_count > 0 && (
                                    <p>
                                      {copy.excludedLodges(s.excluded_count)}
                                    </p>
                                  )}
                                  <ul>
                                    {s.references?.map((ref: any) => (
                                      <li key={ref.lodge_id}>
                                        {ref.lodge_name} · {ref.timezone}
                                        {ref.period
                                          ? ` · ${formatDate(ref.period.start_date)} – ${formatDate(ref.period.end_date)} (UTC)`
                                          : ref.current_date
                                            ? ` · ${formatDate(ref.current_date)}`
                                            : ""}
                                      </li>
                                    ))}
                                  </ul>
                                  {s.contributors && (
                                    <details>
                                      <summary>{copy.metricCoverage}</summary>
                                      <ul>
                                        {Object.entries(s.contributors).map(
                                          ([metric, ids]) => (
                                            <li key={metric}>
                                              {readableLabel(metric)}:{" "}
                                              {(ids as string[])
                                                .map(
                                                  (id) =>
                                                    s.references?.find(
                                                      (ref: any) =>
                                                        ref.lodge_id === id,
                                                    )?.lodge_name || id,
                                                )
                                                .join(", ")}
                                            </li>
                                          ),
                                        )}
                                      </ul>
                                    </details>
                                  )}
                                </>
                              )}
                              {s.kind === "document" && (
                                <ul>
                                  {s.references?.map((ref: any) => (
                                    <li key={ref.id}>
                                      {knowledgeCopy.source}: {ref.title} ·{" "}
                                      {ref.locator} · {knowledgeCopy.passage}{" "}
                                      {ref.id}
                                    </li>
                                  ))}
                                </ul>
                              )}
                              {s.kind === "memory" && (
                                <>
                                  <p>
                                    {copy.memory} · {copy.period}:{" "}
                                    {formatDate(s.period?.start_date)} –{" "}
                                    {formatDate(s.period?.end_date)}
                                  </p>
                                  <ul>
                                    {s.references?.map((ref: any) => (
                                      <li key={ref.id}>
                                        {copy.event} {ref.id} ·{" "}
                                        {formatDateTime(ref.recorded_at)}
                                      </li>
                                    ))}
                                  </ul>
                                </>
                              )}
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
                  className="textarea"
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
