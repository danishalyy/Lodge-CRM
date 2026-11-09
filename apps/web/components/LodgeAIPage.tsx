"use client";
import { useEffect, useRef, useState } from "react";
import {
  ArrowDown,
  ArrowUpRight,
  BookOpen,
  ChartNoAxesCombined,
  Compass,
  History,
  MessageSquare,
  PanelLeftClose,
  PanelLeftOpen,
  Plus,
  Search,
  ShieldCheck,
  TriangleAlert,
  WifiOff,
  X,
} from "lucide-react";
import { ApiError, aiApi, getActiveLodgeId, getActiveUserId } from "@/lib/api";
import { aiCopy as copy } from "@/lib/strings/ai";
import { formatDateTime } from "@/lib/formatting";
import { Field } from "./ui/field";
import { Button } from "./ui/button";
import Drawer from "./Drawer";
import KnowledgeLibrary from "./KnowledgeLibrary";
import ChatMessage, { Message } from "./ai/ChatMessage";
import ChatComposer from "./ai/ChatComposer";
import ReportLibrary from "./ai/ReportLibrary";
import { reportCopy } from "@/lib/strings/ai-reports";

export default function LodgeAIPage({
  scopeType = "lodge",
  initialReportId,
}: {
  initialReportId?: string;
  scopeType?: "lodge" | "group";
}) {
  const [status, setStatus] = useState<any>(null),
    [conversations, setConversations] = useState<any[]>([]),
    [conversation, setConversation] = useState(""),
    [messages, setMessages] = useState<Message[]>([]),
    [question, setQuestion] = useState(""),
    [error, setError] = useState(""),
    [stage, setStage] = useState<"idle" | "history" | "sending">("idle"),
    [historyOpen, setHistoryOpen] = useState(false),
    [historyCollapsed, setHistoryCollapsed] = useState(false),
    [historySearch, setHistorySearch] = useState(""),
    [knowledgeOpen, setKnowledgeOpen] = useState(false),
    [reportsOpen, setReportsOpen] = useState(Boolean(initialReportId)),
    [showLatest, setShowLatest] = useState(false);
  const generation = useRef(0),
    viewport = useRef<HTMLDivElement>(null),
    followLatest = useRef(true),
    typing = useRef(false);
  const busy = stage !== "idle";
  const ready = status?.state === "ready" && status.tools?.length > 0;
  const scope = () => `${getActiveUserId()}:${getActiveLodgeId()}:${scopeType}`;
  function clearAccess() {
    setConversations([]);
    setHistorySearch("");
    setConversation("");
    setMessages([]);
    setQuestion("");
    setStatus(null);
    setHistoryOpen(false);
    setKnowledgeOpen(false);
    setReportsOpen(false);
  }
  function latest() {
    if (viewport.current)
      viewport.current.scrollTop = viewport.current.scrollHeight;
    followLatest.current = true;
    setShowLatest(false);
  }
  function newConversation() {
    if (busy) return;
    ++generation.current;
    setConversation("");
    setMessages([]);
    setQuestion("");
    setError("");
    setHistoryOpen(false);
    followLatest.current = true;
  }
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
      if (
        !initialReportId &&
        s.knowledge_enabled &&
        !(s.state === "ready" && s.tools?.length)
      )
        setKnowledgeOpen(true);
      if (conversation && !c.some((row: any) => row.id === conversation)) {
        setConversation("");
        setMessages([]);
      }
    } catch (e) {
      if (token === generation.current && origin === scope()) {
        if (e instanceof ApiError && [401, 403, 404, 409].includes(e.status))
          clearAccess();
        setError((e as Error).message);
      }
    }
  }
  useEffect(() => {
    void load();
    const change = () => {
      typing.current = false;
      clearAccess();
      setStage("idle");
      setHistorySearch("");
      void load();
    };
    window.addEventListener("safarios-lodge-changed", change);
    return () => {
      ++generation.current;
      window.removeEventListener("safarios-lodge-changed", change);
    };
  }, [scopeType]);
  useEffect(() => {
    if (followLatest.current) latest();
    else if (messages.length) setShowLatest(true);
  }, [messages, stage]);
  async function open(id: string) {
    const origin = scope(),
      token = ++generation.current;
    setStage("history");
    setError("");
    setHistoryOpen(false);
    followLatest.current = true;
    try {
      const rows = await aiApi.messages(id);
      if (token === generation.current && origin === scope()) {
        setConversation(id);
        setMessages(rows);
      }
    } catch (e) {
      if (token === generation.current && origin === scope()) {
        if (e instanceof ApiError && [401, 403, 404, 409].includes(e.status))
          clearAccess();
        setError((e as Error).message || copy.historyFailed);
      }
    } finally {
      if (token === generation.current && origin === scope()) setStage("idle");
    }
  }
  async function send(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (busy || !question.trim() || typing.current) return;
    typing.current = true;
    let answered = false;
    const origin = scope(),
      token = ++generation.current,
      submitted = question.trim(),
      pendingId = crypto.randomUUID();
    setStage("sending");
    setError("");
    setQuestion("");
    followLatest.current = true;
    setMessages((old) => [
      ...old,
      { id: pendingId, role: "user", content: submitted, pending: true },
    ]);
    try {
      let id = conversation;
      if (!id) {
        const created = await aiApi.create(scopeType);
        if (token !== generation.current || origin !== scope()) return;
        id = created.id;
        setConversation(id);
        setConversations((old) => [
          { ...created, title: submitted.replace(/\s+/g, " ").slice(0, 100) },
          ...old,
        ]);
      }
      const answer = await aiApi.send(id, submitted);
      if (token !== generation.current || origin !== scope()) return;
      if (!answer.content) throw Error(copy.emptyReply);
      answered = true;
      // The final answer is displayed immediately; the private server history then
      // reconciles optimistic IDs and any prior turns (no simulated streaming).
      setMessages((old) => [
        ...old.filter((row) => row.id !== pendingId),
        { id: pendingId, role: "user", content: submitted },
        answer,
      ]);
      const rows = await aiApi.messages(id);
      if (token === generation.current && origin === scope()) setMessages(rows);
    } catch (e) {
      if (token === generation.current && origin === scope()) {
        const denied =
          e instanceof ApiError && [401, 403, 404, 409].includes(e.status);
        if (denied) clearAccess();
        else if (!answered) {
          setMessages((old) => old.filter((row) => row.id !== pendingId));
          setQuestion((draft) => draft || submitted);
        }
        setError(
          answered && !denied
            ? copy.historySyncFailed
            : (e as Error).message || copy.failed,
        );
      }
    } finally {
      if (token === generation.current && origin === scope()) {
        typing.current = false;
        setStage("idle");
      }
    }
  }
  const title = scopeType === "group" ? copy.groupTitle : copy.title;
  const name = status?.scope?.group_name || status?.scope?.lodge_name;
  const selected = conversations.find((c) => c.id === conversation);
  const filtered = conversations.filter((c) =>
    (c.title || copy.untitled)
      .toLowerCase()
      .includes(historySearch.toLowerCase()),
  );
  const history = (
    <>
      <div className="aiHistoryHeading">
        <span>{copy.conversations}</span>
        <ShieldCheck size={15} aria-hidden="true" />
      </div>
      <Button
        className="aiNewConversation"
        variant="secondary"
        onClick={newConversation}
        disabled={busy}
      >
        <Plus size={17} />
        {copy.newConversation}
      </Button>
      {conversations.length > 4 && (
        <div className="aiHistorySearch">
          <Search size={15} aria-hidden="true" />
          <Field label={<span className="sr-only">{copy.searchHistory}</span>}>
            <input
              type="search"
              name="history_search"
              placeholder={copy.searchHistory}
              value={historySearch}
              onChange={(e) => setHistorySearch(e.target.value)}
            />
          </Field>
        </div>
      )}
      <nav aria-label={copy.conversations} className="aiHistoryList">
        {filtered.map((c) => (
          <button
            type="button"
            key={c.id}
            className="aiThread"
            aria-current={conversation === c.id ? "true" : undefined}
            disabled={busy}
            onClick={() => open(c.id)}
          >
            <MessageSquare size={15} aria-hidden="true" />
            <span>
              <strong>{c.title || copy.untitled}</strong>
              <time dateTime={c.created_at}>
                {formatDateTime(c.created_at)}
              </time>
            </span>
          </button>
        ))}
      </nav>
      {!filtered.length && (
        <p className="aiHistoryEmpty">
          {conversations.length ? copy.noSearchResults : copy.noHistory}
        </p>
      )}
      <p className="aiHistoryPrivacy">
        <ShieldCheck size={14} aria-hidden="true" />
        {copy.privateHistory}
      </p>
    </>
  );
  return (
    <div className="aiChatPage">
      <header className="aiChatHeader">
        <div className="aiChatHeading">
          <span className="aiHeaderMark" aria-hidden="true">
            <Compass size={22} />
          </span>
          <div>
            <h1>{title}</h1>
            <p>{name || copy.intro}</p>
          </div>
        </div>
        <div className="aiChatHeaderActions">
          {ready && !knowledgeOpen && !reportsOpen && (
            <>
              <Button
                variant="ghost"
                size="icon"
                className="aiHistoryToggle"
                aria-label={copy.toggleHistory}
                title={copy.toggleHistory}
                aria-expanded={historyOpen}
                onClick={() => setHistoryOpen(true)}
              >
                <History size={18} />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                className="aiDesktopHistoryToggle"
                aria-label={
                  historyCollapsed ? copy.showHistory : copy.hideHistory
                }
                title={historyCollapsed ? copy.showHistory : copy.hideHistory}
                aria-expanded={!historyCollapsed}
                onClick={() => setHistoryCollapsed((v) => !v)}
              >
                {historyCollapsed ? (
                  <PanelLeftOpen size={18} />
                ) : (
                  <PanelLeftClose size={18} />
                )}
              </Button>
              <Button
                variant="secondary"
                className="aiHeaderNew"
                aria-label={copy.newConversation}
                title={copy.newConversation}
                onClick={newConversation}
                disabled={busy}
              >
                <Plus size={17} />
                <span>{copy.newConversation}</span>
              </Button>
            </>
          )}
          {status?.knowledge_enabled && scopeType === "lodge" && (
            <Button
              variant="secondary"
              className="aiKnowledgeToggle"
              aria-label={knowledgeOpen ? copy.backToChat : copy.knowledge}
              title={knowledgeOpen ? copy.backToChat : copy.knowledge}
              aria-pressed={knowledgeOpen}
              onClick={() => {
                setKnowledgeOpen((v) => !v);
                setReportsOpen(false);
              }}
            >
              <BookOpen size={17} />
              <span>{knowledgeOpen ? copy.backToChat : copy.knowledge}</span>
            </Button>
          )}
          {status?.report_kinds?.length > 0 && (
            <Button
              variant="secondary"
              className="aiReportsToggle"
              aria-label={reportsOpen ? reportCopy.back : reportCopy.header}
              title={reportsOpen ? reportCopy.back : reportCopy.header}
              aria-pressed={reportsOpen}
              onClick={() => {
                setReportsOpen((v) => !v);
                setKnowledgeOpen(false);
              }}
            >
              <ChartNoAxesCombined size={17} />
              <span>{reportsOpen ? reportCopy.back : reportCopy.header}</span>
            </Button>
          )}
        </div>
      </header>
      {reportsOpen && status?.report_kinds?.length > 0 ? (
        <ReportLibrary
          scopeType={scopeType}
          initialReportId={initialReportId}
          onDenied={(reason) => {
            clearAccess();
            setError(reason);
          }}
        />
      ) : knowledgeOpen && status?.knowledge_enabled ? (
        <KnowledgeLibrary />
      ) : (
        <>
          {(!status || !ready) && (
            <section
              className="aiConnectionState"
              aria-busy={!status && !error}
            >
              <span className="aiWelcomeMark" aria-hidden="true">
                {error ? <TriangleAlert size={26} /> : <WifiOff size={26} />}
              </span>
              <h2>
                {error
                  ? copy.connectionFailed
                  : !status
                    ? copy.loading
                    : status.state === "test_only"
                      ? copy.testOnly
                      : copy.unavailable}
              </h2>
              <p role={error ? "alert" : !status ? "status" : undefined}>
                {error ||
                  (!status
                    ? copy.loadingBody
                    : status.state === "test_only"
                      ? copy.testOnlyBody
                      : copy.unavailableBody)}
              </p>
              {(error || status) && (
                <Button onClick={load} disabled={busy}>
                  {copy.retry}
                </Button>
              )}
            </section>
          )}
          {ready && (
            <div
              className={`aiChatFrame${historyCollapsed ? " aiHistoryCollapsed" : ""}`}
            >
              <aside className="aiHistoryRail">{history}</aside>
              <section
                className="aiConversation"
                aria-label={copy.chat}
                aria-busy={busy}
              >
                <div className="aiConversationBar">
                  <span>
                    <ShieldCheck size={14} aria-hidden="true" />
                    {copy.privateWorkspace}
                  </span>
                  <span className="aiConversationTitle">
                    {selected?.title || copy.newConversation}
                  </span>
                  {scopeType === "group" && (
                    <details className="aiGroupScope">
                      <summary>{copy.groupScope}</summary>
                      <div>
                        <strong>{status.scope.group_name}</strong>
                        <p>
                          {copy.includedLodges}:{" "}
                          {status.scope.lodges
                            .map((l: any) => l.lodge_name)
                            .join(", ")}
                        </p>
                        {status.scope.excluded_count > 0 && (
                          <p>
                            {copy.excludedLodges(status.scope.excluded_count)}
                          </p>
                        )}
                        <p>{copy.groupCoverage}</p>
                      </div>
                    </details>
                  )}
                </div>
                <div
                  className="aiTranscript"
                  ref={viewport}
                  onScroll={() => {
                    const el = viewport.current;
                    if (!el) return;
                    const near =
                      el.scrollHeight - el.scrollTop - el.clientHeight < 96;
                    followLatest.current = near;
                    setShowLatest(!near);
                  }}
                >
                  <div className="aiReadingColumn">
                    {!messages.length && stage !== "history" && (
                      <div className="aiWelcome">
                        <span className="aiWelcomeMark" aria-hidden="true">
                          <Compass size={30} />
                        </span>
                        <span className="eyebrow">{copy.welcomeEyebrow}</span>
                        <h2>{copy.welcome}</h2>
                        <p>
                          {scopeType === "group"
                            ? copy.groupIntro
                            : copy.welcomeBody}
                        </p>
                        <div
                          className="aiSuggestions"
                          aria-label={copy.suggestion}
                        >
                          {status.tools
                            .filter((t: any) => t.suggestion)
                            .slice(0, 4)
                            .map((t: any) => (
                              <button
                                type="button"
                                className="aiSuggestion"
                                disabled={busy}
                                key={t.name}
                                onClick={() => {
                                  setQuestion(t.suggestion);
                                  document
                                    .querySelector<HTMLTextAreaElement>(
                                      ".aiComposer textarea",
                                    )
                                    ?.focus();
                                }}
                              >
                                <span>{t.suggestion}</span>
                                <ArrowUpRight size={16} aria-hidden="true" />
                              </button>
                            ))}
                        </div>
                      </div>
                    )}
                    {stage === "history" ? (
                      <p className="aiThinking" role="status">
                        {copy.loadingConversation}
                      </p>
                    ) : (
                      <div
                        className="aiMessages"
                        role="log"
                        aria-label={copy.chat}
                        aria-live="polite"
                        aria-relevant="additions text"
                      >
                        {messages.map((message) => (
                          <ChatMessage
                            key={message.id}
                            message={message}
                            conversationId={conversation}
                            onDenied={(reason) => {
                              clearAccess();
                              setError(reason);
                            }}
                          />
                        ))}
                      </div>
                    )}
                    {stage === "sending" && (
                      <div className="aiThinking" role="status">
                        <span className="aiAvatar" aria-hidden="true">
                          <Compass size={18} />
                        </span>
                        <span>{copy.busy}</span>
                        <span className="aiThinkingDots" aria-hidden="true">
                          <i />
                          <i />
                          <i />
                        </span>
                      </div>
                    )}
                  </div>
                </div>
                {showLatest && messages.length > 0 && (
                  <Button
                    variant="secondary"
                    size="icon"
                    className="aiJumpLatest"
                    aria-label={copy.latest}
                    title={copy.latest}
                    onClick={latest}
                  >
                    <ArrowDown size={18} />
                  </Button>
                )}
                {error && (
                  <div className="aiChatError" role="alert">
                    <TriangleAlert size={17} aria-hidden="true" />
                    <span>{error}</span>
                    <Button variant="ghost" onClick={load} disabled={busy}>
                      {copy.retry}
                    </Button>
                  </div>
                )}
                <ChatComposer
                  question={question}
                  setQuestion={setQuestion}
                  busy={busy}
                  onSubmit={send}
                />
              </section>
            </div>
          )}
        </>
      )}
      {historyOpen && ready && (
        <Drawer onClose={() => setHistoryOpen(false)}>
          <div className="aiMobileHistory">
            <div className="aiMobileHistoryTop">
              <h2>{copy.conversations}</h2>
              <Button
                variant="ghost"
                size="icon"
                aria-label={copy.closeHistory}
                onClick={() => setHistoryOpen(false)}
              >
                <X size={18} />
              </Button>
            </div>
            {history}
          </div>
        </Drawer>
      )}
    </div>
  );
}
