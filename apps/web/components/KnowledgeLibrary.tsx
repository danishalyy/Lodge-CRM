"use client";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";
import {
  ApiError,
  getActiveLodgeId,
  getActiveUserId,
  knowledgeApi,
} from "@/lib/api";
import { knowledgeCopy as c } from "@/lib/strings/knowledge";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { formatDateTime } from "@/lib/formatting";
import Drawer from "./Drawer";
import { Field } from "./ui/field";
import { Form } from "./ui/form";

export default function KnowledgeLibrary() {
  const access = useWorkspaceAccess();
  const enabled =
    access.feature("ai_knowledge") &&
    access.feature("document_knowledge") &&
    access.permission("knowledge.view");
  const manage = access.permission("knowledge.manage");
  const [data, setData] = useState<any>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false),
    [open, setOpen] = useState(false),
    [sharing, setSharing] = useState("private"),
    [confirm, setConfirm] = useState(""),
    [editing, setEditing] = useState<any>(null);
  const generation = useRef(0);
  const scope = () => `${getActiveUserId()}:${getActiveLodgeId()}`;
  async function load() {
    const origin = scope(),
      token = ++generation.current;
    setError("");
    try {
      const result = await knowledgeApi.list();
      if (token === generation.current && origin === scope()) setData(result);
    } catch (e) {
      if (token === generation.current && origin === scope()) {
        setData(null);
        setError((e as Error).message);
      }
    }
  }
  useEffect(() => {
    if (!enabled) return;
    void load();
    const changed = () => {
      ++generation.current;
      setData(null);
      setOpen(false);
      setConfirm("");
      setEditing(null);
      setBusy(false);
      void load();
    };
    window.addEventListener("safarios-lodge-changed", changed);
    return () => {
      ++generation.current;
      window.removeEventListener("safarios-lodge-changed", changed);
    };
  }, [enabled]);
  async function action(run: () => Promise<any>, message: string) {
    if (busy) return;
    const origin = scope();
    setBusy(true);
    setError("");
    try {
      await run();
      if (origin === scope()) {
        toast.success(message);
        setOpen(false);
        setConfirm("");
        setEditing(null);
        await load();
      }
    } catch (e) {
      if (origin === scope()) {
        setError((e as Error).message || c.failed);
        if (e instanceof ApiError && [401, 403, 404, 409].includes(e.status)) {
          setData(null);
          setEditing(null);
          setOpen(false);
          setConfirm("");
        }
      }
    } finally {
      if (origin === scope()) setBusy(false);
    }
  }
  async function upload(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const body = new FormData(e.currentTarget);
    await action(() => knowledgeApi.upload(body), c.uploaded);
  }
  if (!enabled) return null;
  return (
    <section className="panel knowledgeLibrary">
      <div className="toolbar">
        <div>
          <h2>{c.title}</h2>
          <p>{c.intro}</p>
        </div>
        <div className="actions">
          <button className="button secondary" onClick={load} disabled={busy}>
            {c.retry}
          </button>
          {manage && (
            <button
              className="button"
              onClick={() => {
                setSharing("private");
                setOpen(true);
              }}
              disabled={busy}
            >
              {c.add}
            </button>
          )}
        </div>
      </div>
      {error && (
        <p role="alert" className="dangerText">
          {error}
        </p>
      )}
      {!data && !error && <p role="status">{c.loading}</p>}
      {data && !data.processing_available && (
        <p role="status">{c.noProcessing}</p>
      )}
      {data?.partial && <p>{c.partial}</p>}
      {data?.items?.length === 0 && <p>{c.empty}</p>}
      {data?.items?.map((doc: any) => (
        <article key={doc.id} className="aiMessage">
          <h3>{doc.title}</h3>
          <p>
            {c.statuses[doc.status] || c.statuses.uploaded} · {doc.file_name} ·{" "}
            {formatDateTime(doc.created_at)}
          </p>
          {doc.status === "failed" && <p>{c.processFailed}</p>}
          <p>
            {c.visibility}{" "}
            {doc.visibility === "private"
              ? c.private
              : doc.visibility === "department"
                ? c.department
                : c.lodge}
          </p>
          <div className="actions">
            {manage && doc.can_manage && doc.can_retry && (
              <button
                className="button secondary"
                disabled={busy || !data.processing_available}
                onClick={() =>
                  action(() => knowledgeApi.process(doc.id), c.queued)
                }
              >
                {c.process}
              </button>
            )}
            {["ready", "outdated"].includes(doc.status) && (
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => {
                  const origin = scope();
                  void knowledgeApi
                    .download(doc.id)
                    .then((result) => {
                      if (origin === scope())
                        window.location.assign(result.url);
                    })
                    .catch((e) => {
                      if (origin === scope()) setError(e.message);
                    });
                }}
              >
                {c.download}
              </button>
            )}
            {manage && doc.can_manage && (
              <button
                className="button secondary"
                disabled={busy}
                onClick={() => setConfirm(doc.id)}
              >
                {c.remove}
              </button>
            )}
          </div>
          {manage && doc.can_manage && (
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => {
                setSharing(doc.visibility);
                setEditing(doc);
              }}
            >
              {c.changeSharing}
            </button>
          )}
        </article>
      ))}
      {open && (
        <Drawer
          onClose={() => {
            if (!busy) setOpen(false);
          }}
        >
          <h2>{c.add}</h2>
          {error && (
            <p role="alert" className="dangerText">
              {error}
            </p>
          )}
          <Form onSubmit={upload}>
            <Field label={c.titleLabel}>
              <input name="title" required maxLength={160} />
            </Field>
            <Field label={c.file} helper={c.fileHint}>
              <input
                name="file"
                type="file"
                required
                accept=".pdf,.docx,.txt"
              />
            </Field>
            <Field label={c.visibility}>
              <select
                name="visibility"
                value={sharing}
                onChange={(e) => setSharing(e.target.value)}
              >
                <option value="private">{c.private}</option>
                {data?.departments?.length > 0 && (
                  <option value="department">{c.department}</option>
                )}
                {data?.can_share_lodge && (
                  <option value="lodge">{c.lodge}</option>
                )}
              </select>
            </Field>
            {sharing === "department" && (
              <Field label={c.departmentLabel}>
                <select name="department_id" required>
                  <option value="">{c.chooseDepartment}</option>
                  {data?.departments?.map((d: any) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <div className="drawerActions">
              <button
                type="button"
                className="button secondary"
                disabled={busy}
                onClick={() => setOpen(false)}
              >
                {c.cancel}
              </button>
              <button className="button" disabled={busy}>
                {busy ? c.uploading : c.add}
              </button>
            </div>
          </Form>
        </Drawer>
      )}
      {editing && (
        <Drawer
          onClose={() => {
            if (!busy) setEditing(null);
          }}
        >
          <h2>{c.changeSharing}</h2>
          <p>{editing.title}</p>
          {error && (
            <p role="alert" className="dangerText">
              {error}
            </p>
          )}
          <Form
            onSubmit={(e) => {
              e.preventDefault();
              const form = new FormData(e.currentTarget);
              void action(
                () =>
                  knowledgeApi.share(editing.id, {
                    visibility: sharing,
                    department_id:
                      sharing === "department"
                        ? String(form.get("department_id") || "") || null
                        : null,
                  }),
                c.shared,
              );
            }}
          >
            <Field label={c.visibility}>
              <select
                name="visibility"
                value={sharing}
                onChange={(e) => setSharing(e.target.value)}
              >
                <option value="private">{c.private}</option>
                {data?.departments?.length > 0 && (
                  <option value="department">{c.department}</option>
                )}
                {data?.can_share_lodge && (
                  <option value="lodge">{c.lodge}</option>
                )}
              </select>
            </Field>
            {sharing === "department" && (
              <Field label={c.departmentLabel}>
                <select
                  name="department_id"
                  required
                  defaultValue={editing.department_id || ""}
                >
                  <option value="">{c.chooseDepartment}</option>
                  {data?.departments?.map((d: any) => (
                    <option key={d.id} value={d.id}>
                      {d.name}
                    </option>
                  ))}
                </select>
              </Field>
            )}
            <div className="drawerActions">
              <button
                type="button"
                className="button secondary"
                disabled={busy}
                onClick={() => setEditing(null)}
              >
                {c.cancel}
              </button>
              <button className="button" disabled={busy}>
                {c.share}
              </button>
            </div>
          </Form>
        </Drawer>
      )}
      {confirm && (
        <Drawer
          onClose={() => {
            if (!busy) setConfirm("");
          }}
        >
          <h2>{c.confirmRemove}</h2>
          <div className="drawerActions">
            <button
              className="button secondary"
              disabled={busy}
              onClick={() => setConfirm("")}
            >
              {c.cancel}
            </button>
            <button
              className="button"
              disabled={busy}
              onClick={() =>
                action(() => knowledgeApi.remove(confirm), c.removed)
              }
            >
              {c.remove}
            </button>
          </div>
        </Drawer>
      )}
    </section>
  );
}
