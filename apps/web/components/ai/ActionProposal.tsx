"use client";
import { useEffect, useRef, useState } from "react";
import { Check, ClipboardCheck, X } from "lucide-react";
import { aiApi, ApiError, getActiveUserId, getActiveLodgeId } from "@/lib/api";
import { actionCopy as copy } from "@/lib/strings/ai-actions";
import { readableLabel } from "@/lib/strings/content";
import { formatDate, formatDateTime } from "@/lib/formatting";
import { Button } from "@/components/ui/button";
import Drawer from "@/components/Drawer";
import { toast } from "sonner";
export type Proposal = {
  id: string;
  action: keyof typeof copy.kinds;
  status: string;
  expires_at: string;
  preview: {
    fields: { key: string; value: unknown; previous?: string | null }[];
  };
  result?: { id: string; status: string };
};
export default function ActionProposal({
  proposal,
  conversationId,
  onDenied,
}: {
  proposal: Proposal;
  conversationId: string;
  onDenied: (message: string) => void;
}) {
  const [row, setRow] = useState(proposal),
    [review, setReview] = useState<(Proposal & { token: string }) | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const reviewButton = useRef<HTMLButtonElement>(null);
  const wasReviewing = useRef(false);
  useEffect(() => {
    if (wasReviewing.current && !review)
      requestAnimationFrame(() => reviewButton.current?.focus());
    wasReviewing.current = Boolean(review);
  }, [review]);
  const mounted = useRef(true),
    pending = useRef(false),
    scope = useRef(`${getActiveUserId()}:${getActiveLodgeId()}`);
  const current = () =>
    mounted.current &&
    scope.current === `${getActiveUserId()}:${getActiveLodgeId()}`;
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  useEffect(() => {
    setRow(proposal);
  }, [proposal]);
  const [now, setNow] = useState(Date.now());
  useEffect(() => {
    if (row.status !== "pending") return;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [row.status]);
  const expired =
    row.status === "expired" ||
    (row.status === "pending" && Date.parse(row.expires_at) <= now);
  async function act(kind: "review" | "confirm" | "cancel") {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      const result = await aiApi.action(
        conversationId,
        row.id,
        kind,
        kind === "confirm" ? review?.token : undefined,
      );
      if (!current()) return;
      if (kind === "review") setReview(result);
      else {
        setRow(result);
        setReview(null);
        toast.success(
          kind === "confirm" ? copy.saved[row.action] : copy.cancelled,
        );
      }
    } catch (e) {
      if (!current()) return;
      setReview(null);
      if (
        e instanceof ApiError &&
        ([401, 403, 404].includes(e.status) ||
          (e.status === 409 && /access changed|account changed/i.test(e.message)))
      )
        onDenied(e.message);
      else {
        setError((e as Error).message);
        if (e instanceof ApiError && e.status === 409)
          setRow((old) => ({ ...old, status: "unavailable" }));
      }
    } finally {
      pending.current = false;
      if (current()) setBusy(false);
    }
  }
  function value(key: string, raw: unknown): string {
    if (raw === null || raw === undefined) return "—";
    if (typeof raw === "boolean") return raw ? copy.yes : copy.no;
    if (["due_at", "scheduled_for"].includes(key))
      return formatDateTime(String(raw));
    if (key === "recurrence_end_date") return formatDate(String(raw));
    if (
      [
        "status",
        "priority",
        "job_type",
        "room_status",
        "vehicle_status",
      ].includes(key)
    )
      return readableLabel(String(raw));
    return String(raw);
  }
  const title = copy.kinds[row.action] || copy.proposal;
  return (
    <div className="aiActionProposal">
      <div className="aiActionHeading">
        <ClipboardCheck size={18} aria-hidden="true" />
        <strong>{title}</strong>
      </div>
      {row.preview.fields.slice(0, 3).map((field, i) => (
        <p key={i}>
          <span>
            {copy.fields[field.key as keyof typeof copy.fields] ||
              readableLabel(field.key)}
          </span>{" "}
          {value(field.key, field.value)}
        </p>
      ))}
      <p className="aiActionState" role="status">
        {row.status === "confirmed" ? (
          <>
            <Check size={15} />
            {copy.confirmed}
          </>
        ) : row.status === "cancelled" ? (
          copy.cancelled
        ) : expired ? (
          copy.expired
        ) : row.status === "unavailable" ? (
          copy.unavailable
        ) : (
          copy.nothingChanged
        )}
      </p>
      {row.status === "pending" && !expired && (
        <div className="actions">
          <Button
            variant="secondary"
            ref={reviewButton}
            onClick={() => act("review")}
            disabled={busy}
          >
            {copy.review}
          </Button>
          <Button variant="ghost" onClick={() => act("cancel")} disabled={busy}>
            {copy.cancelProposal}
          </Button>
        </div>
      )}
      {error && (
        <p role="alert" className="dangerText">
          {error}
        </p>
      )}
      {review && (
        <Drawer
          onClose={() => {
            if (!busy) setReview(null);
          }}
        >
          <div className="aiActionReviewHeader">
            <h2>{title}</h2>
            <Button
              variant="ghost"
              size="icon"
              aria-label={copy.close}
              disabled={busy}
              onClick={() => setReview(null)}
            >
              <X size={18} />
            </Button>
          </div>
          <p>{copy.reviewHint}</p>
          <dl className="aiActionDetails">
            {review.preview.fields.map((field, i) => (
              <div key={i}>
                <dt>
                  {copy.fields[field.key as keyof typeof copy.fields] ||
                    readableLabel(field.key)}
                </dt>
                <dd>
                  {value(field.key, field.value)}
                  {field.previous !== undefined && (
                    <small>
                      {copy.previous}: {value(field.key, field.previous)}
                    </small>
                  )}
                </dd>
              </div>
            ))}
          </dl>
          <p className="muted">
            {copy.expires}: {formatDateTime(review.expires_at)}
          </p>
          <div className="drawerActions">
            <Button
              variant="secondary"
              disabled={busy}
              onClick={() => setReview(null)}
            >
              {copy.cancel}
            </Button>
            <Button disabled={busy || expired} onClick={() => act("confirm")}>
              {busy ? copy.applying : copy.confirm}
            </Button>
          </div>
        </Drawer>
      )}
    </div>
  );
}
