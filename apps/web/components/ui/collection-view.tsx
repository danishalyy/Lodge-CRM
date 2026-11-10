"use client";
import { StatusBoard, type BoardActions } from "./status-board";
import { toast } from "sonner";
import React, {
  Children,
  cloneElement,
  isValidElement,
  useEffect,
  useState,
} from "react";
import {
  Search,
  List,
  LayoutGrid,
  Columns3,
  X,
  Ellipsis,
  Inbox,
} from "lucide-react";
import Drawer from "../Drawer";
import { getActiveLodgeId, getActiveUserId } from "@/lib/api";
import { uiCopy as c } from "@/lib/strings/redesign";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { readableLabel } from "@/lib/strings/content";
type Node = React.ReactNode;
function flat(node: Node): React.ReactElement<any>[] {
  return Children.toArray(node).flatMap((n) =>
    isValidElement(n)
      ? n.type === React.Fragment
        ? flat((n.props as any).children)
        : [n as React.ReactElement<any>]
      : [],
  );
}
function find(node: Node, type: string): React.ReactElement<any> | undefined {
  for (const n of flat(node)) {
    if (n.type === type) return n;
    const child = find(n.props.children, type);
    if (child) return child;
  }
}
function text(node: Node): string {
  if (node == null || typeof node === "boolean") return "";
  if (typeof node === "string" || typeof node === "number") return String(node);
  if (Array.isArray(node)) return node.map(text).join(" ");
  if (isValidElement(node)) {
    const p = node.props as any;
    return (
      text(p.children) ||
      (typeof p.value === "string" ? readableLabel(p.value) : "")
    );
  }
  return "";
}
function status(node: Node): string {
  for (const n of flat(node)) {
    if (
      typeof n.props.value === "string" &&
      (typeof n.type !== "string" || n.type === "select")
    )
      return n.props.value;
    const nested = status(n.props.children);
    if (nested) return nested;
  }
  return "";
}
function replaceBody(node: Node, rows: React.ReactElement[]): Node {
  return Children.map(node, (n) => {
    if (!isValidElement(n)) return n;
    const p = n.props as any;
    if (n.type === "tbody")
      return cloneElement(n as React.ReactElement<any>, {}, rows);
    return p.children
      ? cloneElement(
          n as React.ReactElement<any>,
          {},
          replaceBody(p.children, rows),
        )
      : n;
  });
}
export function CollectionView({
  children,
  loading = false,
  error = false,
  onRetry,
  defaultView = "list",
  name = "records",
  showSearch = true,
  statusBoard,
}: {
  children: Node;
  loading?: boolean;
  error?: boolean;
  onRetry?: () => void;
  defaultView?: "list" | "cards" | "board";
  name?: string;
  showSearch?: boolean;
  statusBoard?: BoardActions;
}) {
  const access = useWorkspaceAccess();
  const [view, setView] = useState(defaultView),
    [query, setQuery] = useState(() =>
      typeof window === "undefined"
        ? ""
        : new URLSearchParams(location.search).get("search") || "",
    ),
    [filter, setFilter] = useState(""),
    [selected, setSelected] = useState<string[]>([]),
    [detail, setDetail] = useState<React.ReactElement<any> | null>(null),
    [review, setReview] = useState(false),
    [saved, setSaved] = useState<any>(null);
  useEffect(() => {
    setDetail(null);
    setReview(false);
    setSelected([]);
  }, [access.scopeKey]);
  useEffect(() => {
    const records = flat(find(children, "tbody")?.props.children).filter(
      (r) => r.type === "tr",
    );
    setDetail((old) =>
      old ? records.find((r) => r.key === old.key) || null : null,
    );
    setSelected((old) =>
      old.filter((id) =>
        records.some((r, index) => String(r.key ?? index) === id),
      ),
    );
  }, [children]);
  const key = `safarios-view:${getActiveUserId()}:${getActiveLodgeId()}:${name}`;
  useEffect(() => {
    try {
      const value = JSON.parse(localStorage.getItem(key) || "null");
      if (
        value &&
        ["list", "board", "cards"].includes(value.view) &&
        typeof value.query === "string" &&
        typeof value.filter === "string"
      )
        setSaved(value);
    } catch {}
  }, [key]);
  const viewKey = `safarios-record-view:${getActiveUserId()}:${getActiveLodgeId()}:${name}`;
  useEffect(() => {
    try {
      const value = localStorage.getItem(viewKey);
      setView(
        value === "list" || value === "cards" || value === "board"
          ? value
          : defaultView,
      );
    } catch {
      setView(defaultView);
    }
  }, [viewKey, defaultView]);
  function changeView(value: "list" | "cards" | "board") {
    setView(value);
    try {
      localStorage.setItem(viewKey, value);
    } catch {}
  }
  const table = find(children, "table"),
    head = find(table, "thead"),
    body = find(table, "tbody");
  if (!table || !body) return <>{children}</>;
  const headers = flat(find(head, "tr")?.props.children).map((h) =>
    text(h.props.children),
  );
  const rows = flat(body.props.children).filter((n) => n.type === "tr");
  const stateIndex = headers.findIndex((h) => h.toLowerCase() === "status");
  const rowState = (r: React.ReactElement<any>) => {
    const cells = flat(r.props.children);
    return stateIndex < 0
      ? ""
      : status(cells[stateIndex]?.props.children) ||
          text(cells[stateIndex]?.props.children);
  };
  const states = [...new Set(rows.map(rowState).filter(Boolean))];
  const filtered = rows.filter(
    (r) =>
      (!query || text(r).toLowerCase().includes(query.toLowerCase())) &&
      (!filter || rowState(r) === filter),
  );
  const rowKey = (r: React.ReactElement<any>, index: number) =>
    String(r.props["data-record-id"] ?? r.key ?? index);
  function open(r: React.ReactElement<any>, event?: React.MouseEvent) {
    const first = flat(r.props.children)[0];
    const button = find(first?.props.children, "button");
    if (button?.props.onClick) {
      button.props.onClick(event);
      return;
    }
    setDetail(r);
  }
  function card(r: React.ReactElement<any>, index: number) {
    const cells = flat(r.props.children),
      id = rowKey(r, index),
      title =
        text(
          find(cells[0]?.props.children, "strong")?.props.children ||
            find(cells[0]?.props.children, "b")?.props.children ||
            cells[0]?.props.children,
        )
          .replace(/\s+/g, " ")
          .trim() || c.unnamed;
    return (
      <article className="recordCard" key={id}>
        <header className="recordCardHeader">
          <span className="recordAvatar" aria-hidden="true">
            {title
              .split(" ")
              .slice(0, 2)
              .map((s) => s[0])
              .join("")}
          </span>
          <button
            type="button"
            className="linkButton"
            onClick={(event) => open(r, event)}
          >
            {title}
          </button>
          <label className="recordSelection">
            <input
              type="checkbox"
              aria-label={c.select + " " + title}
              checked={selected.includes(id)}
              onChange={(e) =>
                setSelected((old) =>
                  e.target.checked ? [...old, id] : old.filter((x) => x !== id),
                )
              }
            />
          </label>
        </header>
        {find(cells[0]?.props.children, "small") && (
          <p className="recordSubtitle">
            {find(cells[0]?.props.children, "small")?.props.children}
          </p>
        )}
        <div className="recordCardFields">
          {cells.slice(1).map((cell, i) =>
            headers[i + 1] && headers[i + 1] !== "Workflow" ? (
              <div key={i}>
                <span>{headers[i + 1]}</span>
                <span>{cell.props.children}</span>
              </div>
            ) : null,
          )}
        </div>
        <div className="recordActions">
          {cells.map((cell, i) =>
            !headers[i] || headers[i] === "Workflow" ? (
              <React.Fragment key={i}>{cell.props.children}</React.Fragment>
            ) : null,
          )}
        </div>
      </article>
    );
  }
  const displayedRows = filtered.map((r, i) =>
    cloneElement(r, {
      onClick: (event: React.MouseEvent) => {
        if (
          (event.target as HTMLElement).closest(
            "a,button,input,select,textarea,label",
          )
        )
          return;
        open(r, event);
      },
      children: flat(r.props.children).map((cell, j) =>
        j === 0
          ? cloneElement(
              cell,
              {},
              <>
                <button
                  className="recordOpen linkButton"
                  type="button"
                  aria-label={c.open + " " + text(cell.props.children)}
                  onClick={(event) => open(r, event)}
                >
                  <Ellipsis size={16} />
                </button>
                {cell.props.children}
              </>,
            )
          : cell,
      ),
    }),
  );
  return (
    <section className="collectionView" data-collection={name}>
      <div className="filterBar">
        {showSearch && (
          <label className="collectionSearch">
            <Search size={16} />
            <span className="sr-only">{c.search}</span>
            <input
              className="field"
              type="search"
              placeholder={c.search}
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
          </label>
        )}
        {states.length > 0 && (
          <select
            className="select"
            aria-label={c.all}
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          >
            <option value="">{c.all}</option>
            {states.map((s) => (
              <option key={s} value={s}>
                {readableLabel(s)}
              </option>
            ))}
          </select>
        )}
        <div className="viewSwitcher" aria-label="Record view">
          {(["list", "cards", "board"] as const).map((v) => (
            <button
              type="button"
              key={v}
              aria-pressed={v === view}
              onClick={() => changeView(v)}
            >
              {v === "list" ? (
                <List size={15} />
              ) : v === "board" ? (
                <Columns3 size={15} />
              ) : (
                <LayoutGrid size={15} />
              )}
              <span>{c[v]}</span>
            </button>
          ))}
        </div>
        <select
          className="select"
          aria-label={c.saved}
          value=""
          onChange={(e) => {
            if (e.target.value === "save") {
              const value = { view, query, filter };
              try {
                localStorage.setItem(key, JSON.stringify(value));
                setSaved(value);
                toast.success(c.viewSaved);
              } catch {
                toast.error(c.viewSaveError);
              }
            } else if (e.target.value === "saved" && saved) {
              changeView(saved.view);
              setQuery(saved.query);
              setFilter(saved.filter);
            } else {
              changeView(defaultView);
              setQuery("");
              setFilter("");
            }
          }}
        >
          <option value="">{c.saved}</option>
          <option value="default">{c.defaultView}</option>
          {saved && <option value="saved">{c.savedView}</option>}
          <option value="save">{c.saveView}</option>
        </select>
      </div>
      {(query || filter) && (
        <div className="filterChips">
          <button
            onClick={() => {
              setQuery("");
              setFilter("");
            }}
          >
            <X size={12} />
            {c.clear}
          </button>
        </div>
      )}
      {selected.length > 0 && (
        <div className="bulkBar">
          <span>{c.selected(selected.length)}</span>
          <button className="button" onClick={() => setReview(true)}>
            {c.review}
          </button>
          <button className="button" onClick={() => setSelected([])}>
            {c.clearSelection}
          </button>
        </div>
      )}
      {error && onRetry && (
        <div className="inlineRetry">
          <button type="button" className="button secondary" onClick={onRetry}>
            {c.retry}
          </button>
        </div>
      )}
      {loading && !rows.length ? (
        <div className="panel collectionSkeleton" role="status">
          <span className="sr-only">{c.loading}</span>
          {Array.from({ length: 4 }, (_, i) => (
            <div className="skeleton" key={i} />
          ))}
        </div>
      ) : error && !rows.length ? null : view === "list" ? (
        replaceBody(children, displayedRows)
      ) : statusBoard ? (
        <StatusBoard
          name={name}
          mode={view === "cards" ? "cards" : "board"}
          actions={statusBoard}
          items={filtered.map((record, index) => {
            const first = flat(record.props.children)[0];
            return {
              id: rowKey(record, index),
              status: rowState(record),
              title: text(
                find(first?.props.children, "strong")?.props.children ||
                  find(first?.props.children, "b")?.props.children ||
                  first?.props.children,
              ).trim(),
              record,
              index,
            };
          })}
          renderCard={(item) => card(item.record, item.index)}
        />
      ) : filtered.length ? (
        view === "cards" ? (
          <div className="collectionCards">{filtered.map(card)}</div>
        ) : (
          <div
            className="collectionBoard"
            tabIndex={0}
            role="region"
            aria-label={c.board}
          >
            {(states.length ? states : [""]).map((state) => (
              <section className="boardColumn" key={state}>
                <h2>
                  {state ? readableLabel(state) : c.fields}
                  <span>
                    {filtered.filter((r) => rowState(r) === state).length}
                  </span>
                </h2>
                {filtered.filter((r) => rowState(r) === state).map(card)}
              </section>
            ))}
          </div>
        )
      ) : (
        <div className="panel empty">
          <Inbox size={24} />
          <p>{rows.length ? c.noMatches : c.noRecords}</p>
        </div>
      )}
      {view === "list" && rows.length > 0 && !filtered.length && (
        <div className="empty">{c.noMatches}</div>
      )}
      {(detail || review) && (
        <Drawer
          onClose={() => {
            setDetail(null);
            setReview(false);
          }}
        >
          <div className="drawerHead">
            <h2>{review ? c.review : c.details}</h2>
            <button
              className="closeButton"
              aria-label={c.close}
              onClick={() => {
                setDetail(null);
                setReview(false);
              }}
            >
              <X size={20} />
            </button>
          </div>
          {review
            ? rows.filter((r, i) => selected.includes(rowKey(r, i))).map(card)
            : detail && (
                <dl className="collectionRowDetails">
                  {flat(detail.props.children).map((cell, i) => (
                    <div key={i}>
                      <dt>{headers[i] || c.fields}</dt>
                      <dd>{cell.props.children}</dd>
                    </div>
                  ))}
                </dl>
              )}
        </Drawer>
      )}
    </section>
  );
}
