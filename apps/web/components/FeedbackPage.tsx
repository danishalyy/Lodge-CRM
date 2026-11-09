"use client";
import { CollectionView } from "@/components/ui/collection-view";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { TableScroll } from "@/components/ui/table-scroll";

import { readableLabel } from "@/lib/strings/content";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useState } from "react";
import { authApi, operationsApi } from "@/lib/api";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
export default function FeedbackPage() {
  const [collectionLoading, setCollectionLoading] = useState(true);
  const access = useWorkspaceAccess();
  const [rows, setRows] = useState<any[]>([]),
    [guests, setGuests] = useState<any[]>([]),
    [deps, setDeps] = useState<any[]>([]),
    [staff, setStaff] = useState<any[]>([]),
    [open, setOpen] = useState(false),
    [error, setError] = useState(""),
    [canManage, setCanManage] = useState(false);
  const load = async () => {
    if (!access.isCurrent()) return;
    setCollectionLoading(true);
    try {
      const me = await authApi.me();
      const active = localStorage.getItem("active_lodge_id");
      const m = me.memberships?.find((x: any) => x.lodge_id === active);
      setCanManage(m?.permissions?.includes("feedback.manage"));
      const [r, d, s] = await Promise.all([
        operationsApi.feedback.list(),
        access.permission("feedback.manage") &&
        access.feature("departments") &&
        access.permission("departments.view")
          ? operationsApi.departments.list()
          : Promise.resolve([]),
        access.permission("feedback.manage") &&
        access.feature("staff") &&
        access.permission("staff.view")
          ? operationsApi.staff.list()
          : Promise.resolve([]),
      ]);
      if (!access.isCurrent()) return;
      setRows(r);
      setDeps(d);
      setStaff(s);
      try {
        const resolvedChoices =
          access.permission("feedback.manage") &&
          access.feature("guests") &&
          access.permission("guests.view")
            ? await (await import("@/lib/api")).lodgeApi.guests()
            : [];
        if (!access.isCurrent()) return;
        setGuests(resolvedChoices);
      } catch {
        setGuests([]);
      }
    } catch (e: any) {
      setError(e.message);
    } finally {
      setCollectionLoading(false);
    }
  };
  useEffect(() => {
    setOpen(false);
    setStaff([]);
    setGuests([]);
    setDeps([]);
    load();
  }, [access.scopeKey]);
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!access.permission("feedback.manage")) return;
    const f = new FormData(e.currentTarget);
    await operationsApi.feedback.create({
      guest_id: String(f.get("guest_id")),
      department_id: f.get("department_id") || null,
      assigned_staff_id: f.get("assigned_staff_id") || null,
      feedback_type: String(f.get("feedback_type")),
      category: String(f.get("category")),
      rating: f.get("rating") ? Number(f.get("rating")) : null,
      comments: String(f.get("comments") || ""),
      follow_up_required: f.get("follow_up_required") === "on",
    });
    setOpen(false);
    load();
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">GUEST EXPERIENCE</span>
          <h1>Feedback & Complaints</h1>
          <p>
            Track compliments, feedback and complaints through follow-up and
            resolution.
          </p>
        </div>
        {canManage && access.permission("feedback.manage") && (
          <button className="button primary" onClick={() => setOpen(true)}>
            + Feedback
          </button>
        )}
      </div>
      {error && <div className="panel dangerText">{error}</div>}
      <CollectionView
        loading={collectionLoading}
        error={Boolean(error)}
        onRetry={() => {
          setError("");
          void load();
        }}
        name="FeedbackPage"
        defaultView="list"
      >
        <TableScroll as="section" className="panel tableWrap">
          <table className="dataTable">
            <thead>
              <tr>
                <th>Guest</th>
                <th>Type</th>
                <th>Category</th>
                <th>Rating</th>
                <th>Assigned</th>
                <th>Status</th>
                <th>Follow-up</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>
                    <strong>{r.guest_name}</strong>
                    <br />
                    <small>{r.comments || "—"}</small>
                  </td>
                  <td>{r.feedback_type}</td>
                  <td>{r.category}</td>
                  <td>{r.rating || "—"}</td>
                  <td>{r.assigned_staff_name || "—"}</td>
                  <td>
                    <StatusPill value={r.status} />
                  </td>
                  <td>{r.follow_up_required ? "Required" : "No"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {!rows.length && (
            <div className="empty">No guest feedback has been recorded.</div>
          )}
        </TableScroll>
      </CollectionView>
      {open && access.permission("feedback.manage") && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <h1>Record feedback</h1>
            <button
              className="closeButton"
              onClick={() => setOpen(false)}
              aria-label="Close dialog"
              type="button"
            >
              ×
            </button>
          </div>
          <Form onSubmit={create}>
            <Field label="Guest">
              <select className="select" name="guest_id" required>
                <option value="">Select guest</option>
                {guests.map((g) => (
                  <option key={g.id} value={g.id}>
                    {g.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Type">
              <select className="select" name="feedback_type">
                <option value="feedback">{readableLabel("feedback")}</option>
                <option value="compliment">
                  {readableLabel("compliment")}
                </option>
                <option value="complaint">{readableLabel("complaint")}</option>
              </select>
            </Field>
            <Field label="Category">
              <input
                className="field"
                name="category"
                defaultValue="general"
                required
              />
            </Field>
            <Field label="Rating">
              <select className="select" name="rating">
                <option value="">Not provided</option>
                {[1, 2, 3, 4, 5].map((x) => (
                  <option key={x}>{x}</option>
                ))}
              </select>
            </Field>
            <Field label="Department">
              <select className="select" name="department_id">
                <option value="">None</option>
                {deps.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Assigned staff">
              <select className="select" name="assigned_staff_id">
                <option value="">Unassigned</option>
                {staff.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.full_name}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="Comments">
              <textarea className="textarea" name="comments" />
            </Field>
            <label className="checkRow">
              <span>Follow-up required</span>
              <input type="checkbox" name="follow_up_required" />
            </label>
            <button className="button primary">Save feedback</button>
          </Form>
        </Drawer>
      )}
    </>
  );
}
