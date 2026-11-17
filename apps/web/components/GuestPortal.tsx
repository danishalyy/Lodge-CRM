"use client";
import { useCallback, useEffect, useRef, useState, FormEvent } from "react";
import Link from "next/link";
import { EmailOtpFields, useEmailSignIn } from "./EmailOtpFields";
import { emailSignInCopy as emailCopy } from "@/lib/strings/email-sign-in";
import Markdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  CalendarDays,
  BookOpen,
  MessageSquare,
  Bell,
  Compass,
  Send,
  LogOut,
} from "lucide-react";
import { toast } from "sonner";
import SafariBrand from "./SafariBrand";
import ThemeToggle from "./ThemeToggle";
import AccountSecurity from "./AccountSecurity";
import { Field } from "./ui/field";
import { Form } from "./ui/form";
import { PasswordField } from "./ui/password-field";
import { ConfirmDialog } from "./ui/confirm-dialog";
import StatusPill from "./StatusPill";
import {
  ApiError,
  authApi,
  guestApi,
  getActiveUserId,
  type GuestScope,
} from "@/lib/api";
import { portalCopy as c } from "@/lib/strings/guest-portal";

type Access = {
  id: string;
  lodge_name: string;
  arrival_date: string;
  departure_date: string;
};
type Content = {
  id: string;
  kind: keyof typeof c.kinds;
  title: string;
  body: string;
};
type Snapshot = {
  access_id: string;
  user_id: string;
  guest_name: string;
  lodge: {
    name: string;
    timezone: string;
    date_format: string;
    has_logo: boolean;
  };
  stay: {
    arrival_date: string;
    departure_date: string;
    party_size: number;
    room: string | null;
  };
  content: Content[];
  features: Record<string, boolean>;
  read_only: boolean;
  ai_configured: boolean;
};
type Turn = {
  id: string;
  question: string;
  answer: string;
  sources: { id: string; kind: string; label: string }[];
};
type Tab = "stay" | "information" | "requests" | "updates" | "assistant";
const key = (scope: GuestScope) => scope.userId + ":" + scope.accessId;
function dateLabel(value: string, zone = "UTC", format = "locale") {
  const day = /^\d{4}-\d{2}-\d{2}$/.test(value);
  if (format !== "locale") {
    const date = new Date(day ? value + "T00:00:00Z" : value);
    const fields = new Intl.DateTimeFormat(undefined, {
      timeZone: day ? "UTC" : zone,
      day: "2-digit",
      month: "2-digit",
      year: "numeric",
    }).formatToParts(date);
    const part = (kind: string) =>
      fields.find((row) => row.type === kind)?.value || "";
    const dateText =
      format === "dd/MM/yyyy"
        ? `${part("day")}/${part("month")}/${part("year")}`
        : format === "MM/dd/yyyy"
          ? `${part("month")}/${part("day")}/${part("year")}`
          : format === "yyyy-MM-dd"
            ? `${part("year")}-${part("month")}-${part("day")}`
            : new Intl.DateTimeFormat(undefined, {
                dateStyle: "medium",
                timeZone: day ? "UTC" : zone,
              }).format(date);
    return day
      ? dateText
      : dateText +
          " · " +
          new Intl.DateTimeFormat(undefined, {
            timeStyle: "short",
            timeZone: zone,
          }).format(date);
  }
  return new Intl.DateTimeFormat(
    undefined,
    day
      ? { dateStyle: "medium", timeZone: "UTC" }
      : { dateStyle: "medium", timeStyle: "short", timeZone: zone },
  ).format(new Date(day ? value + "T00:00:00Z" : value));
}
export default function GuestPortal({
  security = false,
}: {
  security?: boolean;
}) {
  const emailFlow = useEmailSignIn();
  const [mode, setMode] = useState<"checking" | "login" | "wrong" | "guest">(
    "checking",
  );
  const [user, setUser] = useState<any>(null),
    [stays, setStays] = useState<Access[]>([]),
    [data, setData] = useState<Snapshot | null>(null);
  const [trips, setTrips] = useState<any[]>([]),
    [requests, setRequests] = useState<any[]>([]),
    [notices, setNotices] = useState<any[]>([]),
    [messages, setMessages] = useState<Turn[]>([]);
  const [tab, setTab] = useState<Tab>("stay"),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [loading, setLoading] = useState(false),
    [clear, setClear] = useState(false);
  const [email, setEmail] = useState(""),
    [password, setPassword] = useState("");
  const [description, setDescription] = useState(""),
    [kind, setKind] = useState("general"),
    [question, setQuestion] = useState(""),
    [pending, setPending] = useState("");
  const alive = useRef(false),
    generation = useRef(0),
    refreshEpoch = useRef(0),
    scope = useRef<GuestScope | null>(null),
    locked = useRef(false),
    command = useRef<{ body: string; id: string } | null>(null),
    chatCommand = useRef<{ body: string; id: string } | null>(null);
  const turnList = useRef<HTMLDivElement>(null);
  useEffect(() => {
    if (turnList.current)
      turnList.current.scrollTop = turnList.current.scrollHeight;
  }, [messages.length, pending, tab]);
  const active = (origin: GuestScope) =>
    alive.current &&
    scope.current &&
    key(scope.current) === key(origin) &&
    getActiveUserId() === origin.userId;
  const resetPrivate = useCallback(() => {
    scope.current = null;
    generation.current++;
    refreshEpoch.current++;
    locked.current = false;
    setData(null);
    setTrips([]);
    setRequests([]);
    setNotices([]);
    setMessages([]);
    setDescription("");
    setQuestion("");
    setPending("");
    setTab("stay");
    setClear(false);
    command.current = null;
    chatCommand.current = null;
    setBusy(false);
    setLoading(false);
  }, []);
  function actionError(origin: GuestScope, error: unknown) {
    if (!active(origin)) return;
    if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
      resetPrivate();
      setStays([]);
      if (error.status === 401) {
        setUser(null);
        setMode("login");
      }
    }
    setError(error instanceof Error ? error.message : c.invalidStay);
  }
  async function load(origin: GuestScope) {
    const epoch = ++refreshEpoch.current;
    const current = () => active(origin) && refreshEpoch.current === epoch;
    try {
      const snapshot = (await guestApi.snapshot(origin)) as Snapshot;
      if (!current()) return;
      const [schedule, ownRequests, updates, history] = await Promise.all([
        snapshot.features.activities || snapshot.features.transfers
          ? guestApi.itinerary(origin)
          : [],
        snapshot.features.requests ? guestApi.requests(origin) : [],
        snapshot.features.notifications ? guestApi.notices(origin) : [],
        snapshot.features.ai ? guestApi.messages(origin) : [],
      ]);
      if (!current()) return;
      setData(snapshot);
      setTrips(schedule);
      setRequests(ownRequests);
      setNotices(updates);
      setMessages(history);
      setError("");
      setTab((old) =>
        (old === "requests" && !snapshot.features.requests) ||
        (old === "updates" && !snapshot.features.notifications) ||
        (old === "assistant" && !snapshot.features.ai)
          ? "stay"
          : old,
      );
    } catch (e) {
      if (current()) actionError(origin, e);
    } finally {
      if (current()) setLoading(false);
    }
  }
  async function openStay(id: string, userId = user?.id) {
    resetPrivate();
    setError("");
    if (!id || !userId) return;
    const origin = { userId, accessId: id };
    scope.current = origin;
    setLoading(true);
    await load(origin);
  }
  async function initialize() {
    const version = ++generation.current;
    setMode("checking");
    setError("");
    try {
      const me = await authApi.me();
      if (!alive.current || version !== generation.current) return;
      if (!me.is_guest) {
        resetPrivate();
        setMode("wrong");
        return;
      }
      setUser(me);
      setMode("guest");
      if (security) return;
      const result = await guestApi.accesses();
      if (!alive.current || version !== generation.current) return;
      setStays(result.stays);
      const requested = new URLSearchParams(location.search).get("access");
      const selected = requested
        ? result.stays.find((row: Access) => row.id === requested)
        : result.stays[0];
      if (selected) await openStay(selected.id, me.id);
      else if (requested) setError(c.invalidStay);
    } catch (e) {
      if (!alive.current || version !== generation.current) return;
      setMode("login");
      if (!(e instanceof ApiError && e.status === 401))
        setError(e instanceof Error ? e.message : c.invalidStay);
    }
  }
  useEffect(() => {
    alive.current = true;
    void initialize();
    const changed = (event: Event) => {
      if (
        event instanceof StorageEvent &&
        event.key &&
        !["active_user_id", "safarios_local_signout"].includes(event.key)
      )
        return;
      resetPrivate();
      emailFlow.reset();
      setPassword("");
      setEmail("");
      setStays([]);
      setUser(null);
      setMode("login");
      setError("");
    };
    window.addEventListener("storage", changed);
    const timer = setInterval(() => {
      const current = scope.current;
      if (current) void load({ ...current });
    }, 15000);
    return () => {
      alive.current = false;
      generation.current++;
      scope.current = null;
      clearInterval(timer);
      window.removeEventListener("storage", changed);
    };
  }, []);
  async function signIn(event: FormEvent) {
    event.preventDefault();
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await guestApi.login(
        email,
        password,
        undefined,
        undefined,
        emailFlow.proof(),
      );
      if (emailFlow.accept(result)) return;
      setPassword("");
      emailFlow.reset();
      await initialize();
    } catch (error) {
      setError(error instanceof Error ? error.message : emailCopy.error);
    } finally {
      locked.current = false;
      setBusy(false);
    }
  }
  async function resend() {
    if (locked.current) return;
    locked.current = true;
    setBusy(true);
    emailFlow.setResending(true);
    setError("");
    try {
      emailFlow.accept(
        await guestApi.login(
          email,
          password,
          undefined,
          undefined,
          emailFlow.proof(true),
        ),
      );
    } catch (error) {
      setError(error instanceof Error ? error.message : emailCopy.error);
    } finally {
      locked.current = false;
      setBusy(false);
      emailFlow.setResending(false);
    }
  }
  async function signOut() {
    resetPrivate();
    setUser(null);
    setStays([]);
    setMode("login");
    await authApi.logout();
  }
  async function sendRequest(event: FormEvent) {
    event.preventDefault();
    const origin = scope.current;
    if (!origin || locked.current || data?.read_only) return;
    const body = JSON.stringify({
      request_type: kind,
      description: description.trim(),
      scope: key(origin),
    });
    if (command.current?.body !== body)
      command.current = { body, id: crypto.randomUUID() };
    locked.current = true;
    setBusy(true);
    setError("");
    try {
      await guestApi.submit(origin, {
        client_reference: command.current.id,
        request_type: kind,
        description: description.trim(),
      });
      if (!active(origin)) return;
      refreshEpoch.current++;
      setDescription((value) =>
        value.trim() === description.trim() ? "" : value,
      );
      command.current = null;
      toast.success(c.requestSent);
      await load(origin);
    } catch (e) {
      actionError(origin, e);
    } finally {
      if (active(origin)) {
        locked.current = false;
        setBusy(false);
      }
    }
  }
  async function ask(event: FormEvent) {
    event.preventDefault();
    const origin = scope.current;
    if (!origin || locked.current || !question.trim() || data?.read_only)
      return;
    const body = key(origin) + ":" + question.trim();
    if (chatCommand.current?.body !== body)
      chatCommand.current = { body, id: crypto.randomUUID() };
    locked.current = true;
    setBusy(true);
    setPending(question.trim());
    setError("");
    try {
      const reply = await guestApi.ask(origin, {
        client_reference: chatCommand.current.id,
        content: question.trim(),
      });
      if (!active(origin)) return;
      refreshEpoch.current++;
      setMessages((old) =>
        old.some((row) => row.id === reply.id) ? old : [...old, reply],
      );
      setQuestion((value) => (value.trim() === question.trim() ? "" : value));
      chatCommand.current = null;
    } catch (e) {
      actionError(origin, e);
    } finally {
      if (active(origin)) {
        locked.current = false;
        setBusy(false);
        setPending("");
      }
    }
  }
  async function clearChat() {
    const origin = scope.current;
    if (!origin || locked.current) return;
    locked.current = true;
    setBusy(true);
    refreshEpoch.current++;
    try {
      await guestApi.clearChat(origin);
      if (active(origin)) {
        refreshEpoch.current++;
        setMessages([]);
        chatCommand.current = null;
        toast.success(c.cleared);
      }
    } catch (e) {
      actionError(origin, e);
    } finally {
      if (active(origin)) {
        locked.current = false;
        setBusy(false);
      }
    }
  }
  const tabs: { id: Tab; label: string; icon: typeof CalendarDays }[] = [
    { id: "stay", label: c.stay, icon: CalendarDays },
    { id: "information", label: c.information, icon: BookOpen },
    ...(data?.features.requests
      ? [{ id: "requests" as Tab, label: c.requests, icon: MessageSquare }]
      : []),
    ...(data?.features.notifications
      ? [{ id: "updates" as Tab, label: c.updates, icon: Bell }]
      : []),
    ...(data?.features.ai
      ? [{ id: "assistant" as Tab, label: c.assistant, icon: Compass }]
      : []),
  ];
  return (
    <main className="guestPortal">
      <header className="guestHeader">
        <Link href="/guest" aria-label="SafariOS">
          <SafariBrand />
        </Link>
        <div className="guestHeaderActions">
          <ThemeToggle />
          {mode === "guest" && (
            <>
              <Link
                className="button secondary"
                href={security ? "/guest" : "/guest/security"}
              >
                {security ? c.back : c.security}
              </Link>
              <button
                className="iconButton"
                aria-label={c.signOut}
                onClick={() => void signOut()}
              >
                <LogOut size={20} />
              </button>
            </>
          )}
        </div>
      </header>
      {mode === "checking" ? (
        <div className="panel statePanel" role="status">
          {c.checking}
        </div>
      ) : mode === "wrong" ? (
        <section className="panel statePanel">
          <h1>{c.label}</h1>
          <p>{c.wrongAccount}</p>
          <button className="button primary" onClick={() => void signOut()}>
            {c.signOut}
          </button>
        </section>
      ) : mode === "login" ? (
        <section className="panel guestLogin">
          <span className="eyebrow">{c.label}</span>
          <h1>{c.title}</h1>
          <p>{c.support}</p>
          {error && (
            <p className="dangerText" role="alert">
              {error}
            </p>
          )}
          <Form onSubmit={signIn}>
            <Field label={c.email}>
              <input
                className="field"
                readOnly={!!emailFlow.challenge}
                name="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                required
              />
            </Field>
            <PasswordField
              label={c.password}
              readOnly={!!emailFlow.challenge}
              name="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
            <EmailOtpFields
              flow={emailFlow}
              busy={busy}
              onResend={() => void resend()}
              onReset={() => {
                emailFlow.reset();
                setPassword("");
                setEmail("");
                setError("");
              }}
            />
            <button
              className="button primary"
              disabled={
                busy ||
                (!!emailFlow.challenge &&
                  (!emailFlow.expires || emailFlow.code.length !== 6))
              }
            >
              {emailFlow.challenge
                ? busy
                  ? emailFlow.resending
                    ? emailCopy.resending
                    : emailCopy.verifying
                  : emailCopy.verify
                : busy
                  ? c.signingIn
                  : c.signIn}
            </button>
          </Form>
          <div className="guestLoginLinks">
            <Link href="/forgot-password?guest=1">{c.forgot}</Link>
            <Link href="/login">{c.staffLogin}</Link>
          </div>
        </section>
      ) : security ? (
        <AccountSecurity showLodgePreferences={false} />
      ) : (
        <>
          {error && (
            <div className="panel dangerText" role="alert">
              {error}{" "}
              <button className="linkButton" onClick={() => void initialize()}>
                {c.retry}
              </button>
            </div>
          )}
          {stays.length > 1 && (
            <Field label={c.choose}>
              <select
                className="field"
                value={data?.access_id || ""}
                onChange={(e) => void openStay(e.target.value)}
              >
                <option value="" disabled>
                  {c.choose}
                </option>
                {stays.map((stay) => (
                  <option value={stay.id} key={stay.id}>
                    {stay.lodge_name} · {dateLabel(stay.arrival_date)}
                  </option>
                ))}
              </select>
            </Field>
          )}
          {loading ? (
            <div className="panel statePanel" role="status">
              {c.checking}
            </div>
          ) : !data ? (
            <section className="panel statePanel">
              <h1>{c.none}</h1>
              <p>{c.noneHint}</p>
              {stays.map((stay) => (
                <button
                  className="button secondary"
                  key={stay.id}
                  onClick={() => void openStay(stay.id)}
                >
                  {c.openStay} · {stay.lodge_name}
                </button>
              ))}
            </section>
          ) : (
            <>
              <section className="guestWelcome">
                {data.lodge.has_logo && (
                  <img
                    className="guestLodgeLogo"
                    src={`/api/v1/guest/access/${data.access_id}/logo`}
                    alt={data.lodge.name}
                  />
                )}
                <div>
                  <span className="eyebrow">
                    {data.lodge.name} · {c.label}
                  </span>
                  <h1>
                    {c.welcome}, {data.guest_name}
                  </h1>
                </div>
              </section>
              {data.read_only && <p className="panel">{c.readOnly}</p>}
              <nav className="guestTabs" aria-label={c.label}>
                {tabs.map((item) => (
                  <button
                    className="button secondary"
                    key={item.id}
                    aria-current={tab === item.id ? "page" : undefined}
                    onClick={() => {
                      setTab(item.id);
                      setError("");
                    }}
                  >
                    <item.icon size={18} />
                    <span>{item.label}</span>
                  </button>
                ))}
              </nav>
              {tab === "stay" && (
                <div className="guestGrid">
                  <section className="panel">
                    <h2>{c.stay}</h2>
                    <dl className="guestStayFacts">
                      <dt>{c.arrival}</dt>
                      <dd>
                        {dateLabel(
                          data.stay.arrival_date,
                          data.lodge.timezone,
                          data.lodge.date_format,
                        )}
                      </dd>
                      <dt>{c.departure}</dt>
                      <dd>
                        {dateLabel(
                          data.stay.departure_date,
                          data.lodge.timezone,
                          data.lodge.date_format,
                        )}
                      </dd>
                      <dt>{c.room}</dt>
                      <dd>{data.stay.room || "—"}</dd>
                      <dt>{c.party}</dt>
                      <dd>{data.stay.party_size}</dd>
                    </dl>
                    {data.features.requests && !data.read_only && (
                      <button
                        className="button primary"
                        onClick={() => setTab("requests")}
                      >
                        {c.newRequest}
                      </button>
                    )}
                  </section>
                  <section className="panel">
                    <h2>{c.itinerary}</h2>
                    {!trips.length ? (
                      <p className="textSecondary">{c.noItinerary}</p>
                    ) : (
                      <ol className="guestItinerary">
                        {trips.map((trip) => (
                          <li key={trip.kind + trip.id}>
                            <div>
                              <strong>{trip.title}</strong>
                              <p>
                                {dateLabel(
                                  trip.starts_at,
                                  data.lodge.timezone,
                                  data.lodge.date_format,
                                )}
                              </p>
                              {trip.location && <p>{trip.location}</p>}
                            </div>
                            <StatusPill value={trip.status} />
                          </li>
                        ))}
                      </ol>
                    )}
                  </section>
                </div>
              )}
              {tab === "information" && (
                <div className="guestInformation">
                  {!data.content.length && (
                    <section className="panel">
                      <h2>{c.information}</h2>
                      <p>{c.noInformation}</p>
                    </section>
                  )}
                  {Object.entries(c.kinds).map(([section, label]) => {
                    const rows = data.content.filter(
                      (row) => row.kind === section,
                    );
                    return rows.length ? (
                      <section className="panel" key={section}>
                        <span className="eyebrow">{label}</span>
                        {rows.map((row) => (
                          <article className="guestPublished" key={row.id}>
                            <h2>{row.title}</h2>
                            <p>{row.body}</p>
                          </article>
                        ))}
                      </section>
                    ) : null;
                  })}
                </div>
              )}
              {tab === "requests" && data.features.requests && (
                <div className="guestGrid">
                  <section className="panel">
                    <h2>{c.newRequest}</h2>
                    <p>{c.requestHint}</p>
                    {!data.read_only && (
                      <Form onSubmit={sendRequest}>
                        <Field label={c.requestKind}>
                          <select
                            className="field"
                            name="request_type"
                            value={kind}
                            onChange={(e) => setKind(e.target.value)}
                          >
                            {Object.entries(c.requestKinds).map(
                              ([value, label]) => (
                                <option value={value} key={value}>
                                  {label}
                                </option>
                              ),
                            )}
                          </select>
                        </Field>
                        <Field label={c.description}>
                          <textarea
                            className="textarea"
                            name="description"
                            required
                            minLength={2}
                            maxLength={2000}
                            value={description}
                            onChange={(e) => setDescription(e.target.value)}
                          />
                        </Field>
                        <button className="button primary" disabled={busy}>
                          {busy ? c.sending : c.sendRequest}
                        </button>
                      </Form>
                    )}
                  </section>
                  <section className="panel">
                    <h2>{c.requests}</h2>
                    {!requests.length ? (
                      <p>{c.noRequests}</p>
                    ) : (
                      requests.map((row) => (
                        <article className="guestPublished" key={row.id}>
                          <StatusPill value={row.status} />
                          <p>{row.description}</p>
                          <small>
                            {dateLabel(
                              row.created_at,
                              data.lodge.timezone,
                              data.lodge.date_format,
                            )}
                          </small>
                        </article>
                      ))
                    )}
                  </section>
                </div>
              )}
              {tab === "updates" && data.features.notifications && (
                <section className="panel">
                  <h2>{c.updates}</h2>
                  {!notices.length ? (
                    <p>{c.noUpdates}</p>
                  ) : (
                    notices.map((notice) => (
                      <article className="guestPublished" key={notice.id}>
                        <h3>{notice.title}</h3>
                        <p>{notice.body}</p>
                        <small>
                          {dateLabel(
                            notice.created_at,
                            data.lodge.timezone,
                            data.lodge.date_format,
                          )}
                        </small>
                        {!notice.read && (
                          <button
                            className="button secondary"
                            onClick={async () => {
                              const origin = scope.current;
                              if (!origin) return;
                              try {
                                await guestApi.readNotice(origin, notice.id);
                                if (active(origin)) {
                                  refreshEpoch.current++;
                                  await load(origin);
                                }
                              } catch (e) {
                                actionError(origin, e);
                              }
                            }}
                          >
                            {c.markRead}
                          </button>
                        )}
                      </article>
                    ))
                  )}
                </section>
              )}
              {tab === "assistant" && data.features.ai && (
                <section className="panel guestChat">
                  <header>
                    <div>
                      <h2>{c.assistant}</h2>
                      <p>{c.askHint}</p>
                    </div>
                    {!!messages.length && (
                      <button
                        className="button secondary"
                        disabled={busy}
                        onClick={() => setClear(true)}
                      >
                        {c.clear}
                      </button>
                    )}
                  </header>
                  {!messages.length && !pending && (
                    <div className="statePanel">
                      <Compass size={32} aria-hidden="true" />
                      <h3>{c.emptyChat}</h3>
                      <p>{c.emptyChatHint}</p>
                    </div>
                  )}
                  <div
                    ref={turnList}
                    className="guestChatTurns"
                    role="region"
                    aria-label={c.conversation}
                    tabIndex={messages.length ? 0 : undefined}
                    aria-live="polite"
                  >
                    {messages.map((row) => (
                      <article key={row.id}>
                        <p className="guestQuestion">
                          <span className="eyebrow">{c.you}</span>
                          {row.question}
                        </p>
                        <div className="aiMarkdown">
                          <Markdown
                            remarkPlugins={[remarkGfm]}
                            skipHtml
                            components={{
                              a: ({ children }) => <span>{children}</span>,
                              img: ({ alt }) => <span>{alt || ""}</span>,
                              h1: ({ children }) => <h3>{children}</h3>,
                              h2: ({ children }) => <h3>{children}</h3>,
                              table: ({ children }) => (
                                <div
                                  className="aiTableWrap"
                                  tabIndex={0}
                                  role="region"
                                  aria-label={c.sources}
                                >
                                  <table>{children}</table>
                                </div>
                              ),
                            }}
                          >
                            {row.answer}
                          </Markdown>
                        </div>
                        {row.sources.length > 0 && (
                          <details>
                            <summary>{c.sources}</summary>
                            <ul>
                              {row.sources.map((source) => (
                                <li key={source.kind + source.id}>
                                  {source.label}
                                </li>
                              ))}
                            </ul>
                          </details>
                        )}
                      </article>
                    ))}
                    {pending && (
                      <article>
                        <p className="guestQuestion">{pending}</p>
                        <p role="status">{c.asking}</p>
                      </article>
                    )}
                  </div>
                  {!data.ai_configured ? (
                    <p>{c.unavailable}</p>
                  ) : !data.content.length && !trips.length ? (
                    <p>{c.noSource}</p>
                  ) : (
                    !data.read_only && (
                      <Form onSubmit={ask} className="guestComposer">
                        <Field label={c.question}>
                          <textarea
                            className="textarea"
                            name="content"
                            required
                            maxLength={2000}
                            value={question}
                            onChange={(e) => setQuestion(e.target.value)}
                          />
                        </Field>
                        <button
                          className="button primary"
                          disabled={busy || !question.trim()}
                        >
                          <Send size={18} />
                          {c.ask}
                        </button>
                      </Form>
                    )
                  )}
                </section>
              )}
            </>
          )}
        </>
      )}
      <ConfirmDialog
        open={clear}
        onOpenChange={setClear}
        title={c.clear}
        description={c.clearConfirm}
        actionLabel={c.clear}
        onConfirm={() => void clearChat()}
      />
    </main>
  );
}
