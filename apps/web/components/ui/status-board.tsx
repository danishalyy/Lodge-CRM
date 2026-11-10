"use client";
import {
  useEffect,
  useId,
  useRef,
  useState,
  ReactNode,
  type KeyboardEvent as ReactKeyboardEvent,
} from "react";
import {
  DndContext,
  MouseSensor,
  TouchSensor,
  useSensor,
  useSensors,
  useDraggable,
  useDroppable,
  pointerWithin,
} from "@dnd-kit/core";
import { GripVertical, ChevronDown, ChevronRight } from "lucide-react";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { getActiveUserId, getActiveLodgeId } from "@/lib/api";
import { readableLabel } from "@/lib/strings/content";
import { boardCopy as c } from "@/lib/strings/boards";
import { ConfirmDialog } from "./confirm-dialog";

type KeyboardMove = {
  id: string;
  status: string;
  scope: string;
  actor: string;
};
export type BoardItem = { id: string; status: string; title: string };
export type BoardActions = {
  columns: readonly string[];
  allowed: (id: string) => readonly string[];
  pending: (id: string) => boolean;
  onMove: (id: string, status: string) => Promise<boolean | void>;
};
export function StatusBoard<T extends BoardItem>({
  name,
  items,
  actions,
  renderCard,
  cardsView = false,
  mode,
  className = "collectionBoard",
}: {
  name: string;
  items: T[];
  actions: BoardActions;
  renderCard: (item: T) => ReactNode;
  cardsView?: boolean;
  mode?: "board" | "cards";
  className?: string;
}) {
  const access = useWorkspaceAccess(),
    instance = useId();
  const storageKey = `safarios-board:${getActiveUserId()}:${getActiveLodgeId()}:${name}`;
  const [collapsed, setCollapsed] = useState<string[]>([]),
    [view, setView] = useState("board"),
    [activeId, setActiveId] = useState<string | null>(null),
    [message, setMessage] = useState("");
  const [confirmation, setConfirmation] = useState<{
    id: string;
    status: string;
  } | null>(null);
  const [keyboardMove, setKeyboardMove] = useState<KeyboardMove | null>(null);
  const keyboardRef = useRef<KeyboardMove | null>(null);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const scope = useRef(access.scopeKey),
    owner = useRef(`${getActiveUserId()}:${getActiveLodgeId()}`),
    locks = useRef(new Set<string>());
  scope.current = access.scopeKey;
  useEffect(() => {
    owner.current = `${getActiveUserId()}:${getActiveLodgeId()}`;
    keyboardRef.current = null;
    setKeyboardMove(null);
    setActiveId(null);
    setConfirmation(null);
    setMessage("");
    locks.current.clear();
  }, [access.scopeKey]);
  useEffect(() => {
    setCollapsed([]);
    setView("board");
    try {
      const saved = JSON.parse(localStorage.getItem(storageKey) || "null");
      if (Array.isArray(saved?.collapsed))
        setCollapsed(
          saved.collapsed.filter((v: unknown) => typeof v === "string"),
        );
      if (["board", "cards"].includes(saved?.view)) setView(saved.view);
    } catch {}
  }, [storageKey]);
  useEffect(() => {
    const cancel = () => {
      if (!keyboardRef.current) return;
      keyboardRef.current = null;
      setKeyboardMove(null);
      setActiveId(null);
      setMessage(c.cancelled);
    };
    document.addEventListener("pointerdown", cancel, true);
    window.addEventListener("blur", cancel);
    return () => {
      document.removeEventListener("pointerdown", cancel, true);
      window.removeEventListener("blur", cancel);
    };
  }, []);
  useEffect(() => {
    keyboardRef.current = null;
    setKeyboardMove(null);
    setActiveId(null);
  }, [mode, view]);
  useEffect(() => {
    if (
      keyboardRef.current &&
      !items.some((item) => item.id === keyboardRef.current?.id)
    ) {
      keyboardRef.current = null;
      setKeyboardMove(null);
      setActiveId(null);
      setMessage(c.cancelled);
    }
  }, [items]);
  function save(next: string[], mode = view) {
    try {
      localStorage.setItem(
        storageKey,
        JSON.stringify({ collapsed: next, view: mode }),
      );
    } catch {}
  }
  const columns = [
    ...new Set([...actions.columns, ...items.map((item) => item.status)]),
  ];
  const active = items.find((item) => item.id === activeId);
  const allowed = (id: string, target: string) => {
    const item = items.find((row) => row.id === id);
    return Boolean(
      item &&
        !access.readOnly &&
        item.status !== target &&
        !actions.pending(id) &&
        actions.allowed(id).includes(target),
    );
  };
  const cardId = (id: string) => `${instance}-${id}`;
  function focusCard(id: string, initial = false) {
    const version = scope.current,
      actor = owner.current;
    requestAnimationFrame(() => {
      if (
        !mounted.current ||
        version !== scope.current ||
        actor !== `${getActiveUserId()}:${getActiveLodgeId()}`
      )
        return;
      const node = document.getElementById(cardId(id)),
        focused = document.activeElement;
      if (
        !node ||
        (focused !== document.body &&
          focused !== node &&
          !(initial && focused && node.contains(focused)))
      )
        return;
      node.scrollIntoView({
        block: "nearest",
        inline: "nearest",
        behavior: "auto",
      });
      node.focus({ preventScroll: true });
    });
  }
  async function commit(id: string, target: string, confirmed = false) {
    const item = items.find((row) => row.id === id);
    keyboardRef.current = null;
    setKeyboardMove(null);
    setActiveId(null);
    if (
      !mounted.current ||
      !item ||
      !allowed(id, target) ||
      locks.current.has(id) ||
      owner.current !== `${getActiveUserId()}:${getActiveLodgeId()}`
    ) {
      setMessage(c.refused(readableLabel(target)));
      if (
        item &&
        !access.readOnly &&
        owner.current === `${getActiveUserId()}:${getActiveLodgeId()}`
      )
        focusCard(id, true);
      return;
    }
    if (target === "cancelled" && !confirmed) {
      setConfirmation({ id, status: target });
      return;
    }
    const origin = scope.current,
      actor = owner.current;
    locks.current.add(id);
    setMessage(c.saving);
    try {
      const operation = actions.onMove(id, target);
      focusCard(id, true);
      const result = await operation;
      if (
        !mounted.current ||
        origin !== scope.current ||
        actor !== `${getActiveUserId()}:${getActiveLodgeId()}`
      )
        return;
      setMessage(
        result === false
          ? c.failed(item.title)
          : c.moved(item.title, readableLabel(target)),
      );
      if (result !== false && collapsed.includes(target)) {
        const next = collapsed.filter((s) => s !== target);
        setCollapsed(next);
        save(next);
      }
      focusCard(id);
    } catch {
      if (mounted.current && origin === scope.current)
        setMessage(c.failed(item.title));
    } finally {
      locks.current.delete(id);
    }
  }
  function onKeyboard(
    id: string,
    event: ReactKeyboardEvent<HTMLButtonElement>,
  ) {
    const code = event.code || (event.key === " " ? "Space" : event.key);
    const move = keyboardRef.current;
    if (!move) {
      if (
        !["Space", "Enter"].includes(code) ||
        event.repeat ||
        isCards ||
        access.readOnly ||
        actions.pending(id) ||
        activeId ||
        !actions.allowed(id).length ||
        owner.current !== `${getActiveUserId()}:${getActiveLodgeId()}`
      )
        return;
      const item = items.find((item) => item.id === id);
      if (!item) return;
      event.preventDefault();
      event.stopPropagation();
      const next = {
        id,
        status: item.status,
        scope: scope.current,
        actor: owner.current,
      };
      keyboardRef.current = next;
      setKeyboardMove(next);
      setActiveId(id);
      setMessage(c.picked(item.title));
      return;
    }
    if (move.id !== id) return;
    const current =
      move.scope === scope.current &&
      move.actor === `${getActiveUserId()}:${getActiveLodgeId()}`;
    const stop = () => {
      keyboardRef.current = null;
      setKeyboardMove(null);
      setActiveId(null);
    };
    if (!current || ["Escape", "Tab"].includes(code)) {
      stop();
      setMessage(c.cancelled);
      if (code !== "Tab") {
        event.preventDefault();
        event.stopPropagation();
      }
      if (current && code === "Escape") {
        const node = document.getElementById(cardId(id));
        node?.scrollIntoView({
          block: "nearest",
          inline: "nearest",
          behavior: "auto",
        });
        node
          ?.querySelector<HTMLButtonElement>(".statusDragHandle")
          ?.focus({ preventScroll: true });
      }
      return;
    }
    if (["Space", "Enter"].includes(code)) {
      event.preventDefault();
      event.stopPropagation();
      if (event.repeat) return;
      stop();
      if (move.status === items.find((item) => item.id === id)?.status)
        setMessage(c.cancelled);
      else void commit(id, move.status);
      return;
    }
    if (["ArrowRight", "ArrowLeft", "ArrowDown", "ArrowUp"].includes(code)) {
      event.preventDefault();
      event.stopPropagation();
      const direction = ["ArrowRight", "ArrowDown"].includes(code) ? 1 : -1;
      const target = columns[columns.indexOf(move.status) + direction];
      if (!target) return;
      const next = { ...move, status: target };
      keyboardRef.current = next;
      setKeyboardMove(next);
      setMessage(
        allowed(id, target)
          ? c.over(readableLabel(target))
          : c.refused(readableLabel(target)),
      );
      document.getElementById(`${instance}-column-${target}`)?.scrollIntoView({
        block: "nearest",
        inline: "nearest",
        behavior: "auto",
      });
    }
  }
  const sensors = useSensors(
    useSensor(MouseSensor, { activationConstraint: { distance: 8 } }),
    useSensor(TouchSensor, {
      activationConstraint: { delay: 250, tolerance: 6 },
    }),
  );
  const isCards = mode === "cards" || (cardsView && view === "cards");
  const content = (item: T) => (
    <StatusCard
      key={item.id}
      item={item}
      cardId={cardId(item.id)}
      draggable={
        !isCards && actions.allowed(item.id).length > 0 && !access.readOnly
      }
      keyboardActive={keyboardMove?.id === item.id && !isCards}
      onKeyboard={(event) => onKeyboard(item.id, event)}
      pending={actions.pending(item.id)}
      columns={columns}
      allowed={(target) => allowed(item.id, target)}
      onMove={(target) => void commit(item.id, target)}
    >
      {renderCard(item)}
    </StatusCard>
  );
  return (
    <>
      {cardsView && (
        <div className="viewSwitcher" aria-label={c.view}>
          {["board", "cards"].map((mode) => (
            <button
              key={mode}
              type="button"
              aria-pressed={view === mode}
              onClick={() => {
                setView(mode);
                save(collapsed, mode);
              }}
            >
              {mode === "board" ? c.board : c.cards}
            </button>
          ))}
        </div>
      )}
      <div
        className="sr-only"
        role="status"
        aria-live="polite"
        aria-atomic="true"
      >
        {message}
      </div>
      <DndContext
        key={access.scopeKey}
        sensors={sensors}
        collisionDetection={pointerWithin}
        accessibility={{
          screenReaderInstructions: { draggable: c.instructions },
          announcements: {
            onDragStart: ({ active }) =>
              c.picked(items.find((i) => i.id === active.id)?.title || ""),
            onDragOver: ({ active, over }) =>
              over
                ? allowed(String(active.id), String(over.id))
                  ? c.over(readableLabel(String(over.id)))
                  : c.refused(readableLabel(String(over.id)))
                : undefined,
            onDragEnd: () => "",
            onDragCancel: () => "",
          },
        }}
        onDragStart={({ active }) => {
          keyboardRef.current = null;
          setKeyboardMove(null);
          setMessage("");
          setActiveId(String(active.id));
        }}
        onDragCancel={() => {
          setActiveId(null);
          setMessage(c.cancelled);
        }}
        onDragEnd={({ active, over }) => {
          setActiveId(null);
          if (
            over &&
            String(over.id) !== items.find((i) => i.id === active.id)?.status
          )
            void commit(String(active.id), String(over.id));
          else setMessage(c.cancelled);
        }}
      >
        {isCards ? (
          <div className="collectionCards">{items.map(content)}</div>
        ) : (
          <div
            className={className + " statusBoard"}
            role="region"
            aria-label={c.board}
            tabIndex={0}
          >
            {columns.map((status) => (
              <StatusColumn
                key={status}
                status={status}
                columnId={`${instance}-column-${status}`}
                keyboardOver={keyboardMove?.status === status}
                preview={
                  keyboardMove?.status === status &&
                  active &&
                  active.status !== status &&
                  allowed(active.id, status)
                    ? active.title
                    : undefined
                }
                count={items.filter((i) => i.status === status).length}
                collapsed={collapsed.includes(status)}
                dropState={
                  active
                    ? allowed(active.id, status)
                      ? "allowed"
                      : "refused"
                    : "idle"
                }
                onToggle={() => {
                  const next = collapsed.includes(status)
                    ? collapsed.filter((s) => s !== status)
                    : [...collapsed, status];
                  setCollapsed(next);
                  save(next);
                }}
              >
                {items.filter((i) => i.status === status).map(content)}
              </StatusColumn>
            ))}
          </div>
        )}
      </DndContext>
      <ConfirmDialog
        open={!!confirmation}
        onOpenChange={(open) => {
          if (!open) {
            setConfirmation(null);
            setMessage(c.cancelled);
          }
        }}
        title={c.cancelTitle}
        description={c.cancelDescription}
        actionLabel={c.cancelAction}
        onConfirm={() => {
          if (confirmation)
            void commit(confirmation.id, confirmation.status, true);
        }}
      />
    </>
  );
}
function StatusColumn({
  status,
  count,
  collapsed,
  dropState,
  columnId,
  keyboardOver,
  preview,
  onToggle,
  children,
}: {
  status: string;
  count: number;
  collapsed: boolean;
  dropState: string;
  columnId: string;
  keyboardOver?: boolean;
  preview?: string;
  onToggle: () => void;
  children: ReactNode;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: status });
  return (
    <section
      ref={setNodeRef}
      id={columnId}
      className="boardColumn statusColumn"
      data-drop-state={dropState}
      data-over={isOver || keyboardOver || undefined}
      data-status={status}
      aria-label={readableLabel(status)}
    >
      <h2>
        <button
          className="linkButton statusColumnToggle"
          type="button"
          aria-label={
            collapsed
              ? c.expand(readableLabel(status))
              : c.collapse(readableLabel(status))
          }
          aria-expanded={!collapsed}
          onClick={onToggle}
        >
          {collapsed ? <ChevronRight size={14} /> : <ChevronDown size={14} />}
          {readableLabel(status)}
          <span>{count}</span>
        </button>
      </h2>
      {preview && (
        <div className="statusKeyboardPreview" aria-hidden="true">
          {preview}
        </div>
      )}
      {!collapsed && (
        <div>
          {children}
          {count === 0 && <p className="muted statusColumnEmpty">{c.empty}</p>}
        </div>
      )}
    </section>
  );
}
function StatusCard({
  item,
  cardId,
  draggable,
  keyboardActive,
  onKeyboard,
  pending,
  columns,
  allowed,
  onMove,
  children,
}: {
  item: BoardItem;
  cardId: string;
  draggable: boolean;
  keyboardActive: boolean;
  onKeyboard: (event: ReactKeyboardEvent<HTMLButtonElement>) => void;
  pending: boolean;
  columns: string[];
  allowed: (status: string) => boolean;
  onMove: (status: string) => void;
  children: ReactNode;
}) {
  const {
    attributes,
    listeners,
    setNodeRef,
    setActivatorNodeRef,
    transform,
    isDragging,
  } = useDraggable({ id: item.id, disabled: !draggable || pending });
  return (
    <div
      id={cardId}
      ref={setNodeRef}
      className="statusBoardItem"
      tabIndex={-1}
      data-record-id={item.id}
      data-dragging={isDragging || keyboardActive || undefined}
      style={
        transform
          ? {
              transform: `translate3d(${transform.x}px, ${transform.y}px, 0)`,
              position: "relative",
              zIndex: 2,
            }
          : undefined
      }
    >
      <div className="statusCardControls">
        <button
          ref={setActivatorNodeRef}
          type="button"
          className="iconButton statusDragHandle"
          {...attributes}
          {...listeners}
          onKeyDown={onKeyboard}
          aria-pressed={isDragging || keyboardActive}
          aria-label={c.move(item.title)}
          disabled={!draggable || pending}
        >
          <GripVertical size={16} />
        </button>
        <select
          className="select"
          aria-label={c.moveTo(item.title)}
          value=""
          disabled={pending || !columns.some(allowed)}
          aria-busy={pending}
          onChange={(event) => {
            const target = event.target.value;
            event.target.value = "";
            onMove(target);
          }}
        >
          <option value="">{pending ? c.saving : c.choose}</option>
          {columns
            .filter((s) => s !== item.status)
            .map((s) => (
              <option key={s} value={s} disabled={!allowed(s)}>
                {readableLabel(s)}
              </option>
            ))}
        </select>
      </div>
      {children}
    </div>
  );
}
