"use client";
import { TableScroll } from "@/components/ui/table-scroll";

import { CountryPicker } from "@/components/ui/country-picker";
import { useWorkspaceAccess } from "@/lib/workspace-access";
import { Field } from "@/components/ui/field";
import { Form } from "@/components/ui/form";
import { FormEvent, useEffect, useMemo, useState, useRef } from "react";
import GuestCommunications from "./GuestCommunications";
import { guestCopy as copy } from "@/lib/strings/guests";
import Drawer from "./Drawer";
import StatusPill from "./StatusPill";
import {
  lodgeApi,
  getActiveLodgeId,
  getActiveUserId,
  ApiError,
} from "@/lib/api";
type Guest = {
  id: string;
  first_name: string;
  last_name: string;
  name: string;
  email?: string;
  phone: string;
  nationality: string;
  vip: boolean;
  dietary_requirements: string;
  allergies: string;
  preferences: string;
  notes: string;
  current_unit?: string;
  stay_status?: string;
  completed_stays: number;
  birthday?: string | null;
  anniversary?: string | null;
  repeat_guest?: boolean;
  safari_preferences?: string;
  anonymized_at?: string | null;
};
export default function GuestsPage() {
  const access = useWorkspaceAccess();
  const canManage = access.permission("guests.manage");
  const [rows, setRows] = useState<Guest[]>([]),
    [q, setQ] = useState(""),
    [selected, setSelected] = useState<Guest | null>(null),
    [open, setOpen] = useState(false),
    [error, setError] = useState("");
  const [loading, setLoading] = useState(true),
    [busy, setBusy] = useState(false);
  const lock = useRef(false),
    generation = useRef(0),
    mounted = useRef(false);
  const context = () => `${getActiveUserId()}:${getActiveLodgeId()}`;
  const scope = useRef(context());
  const actor = useRef({
    userId: getActiveUserId(),
    lodgeId: getActiveLodgeId(),
  });
  const valid = (version: number) =>
    mounted.current &&
    generation.current === version &&
    scope.current === context();
  const load = async () => {
    const version = ++generation.current;
    setLoading(true);
    setError("");
    try {
      const data = await lodgeApi.guests();
      if (valid(version)) setRows(data);
    } catch (e: any) {
      if (valid(version)) {
        if (e instanceof ApiError && [401, 403, 404].includes(e.status)) {
          setRows([]);
          setSelected(null);
        }
        setError(e.message);
      }
    } finally {
      if (valid(version)) setLoading(false);
    }
  };
  useEffect(() => {
    mounted.current = true;
    scope.current = context();
    void load();
    const clear = (event: Event) => {
      if (
        event instanceof StorageEvent &&
        event.key &&
        !["active_user_id", "active_lodge_id"].includes(event.key)
      )
        return;
      generation.current++;
      setRows([]);
      setSelected(null);
      setOpen(false);
      setError("");
    };
    window.addEventListener("safarios-lodge-changed", clear);
    window.addEventListener("storage", clear);
    return () => {
      mounted.current = false;
      generation.current++;
      window.removeEventListener("safarios-lodge-changed", clear);
      window.removeEventListener("storage", clear);
    };
  }, []);
  const list = useMemo(
    () =>
      rows.filter((g) =>
        (g.name + " " + g.nationality + " " + (g.email || ""))
          .toLowerCase()
          .includes(q.toLowerCase()),
      ),
    [rows, q],
  );
  async function create(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (lock.current || !valid(generation.current)) return;
    lock.current = true;
    setBusy(true);
    const version = generation.current;
    const f = new FormData(e.currentTarget);
    try {
      await lodgeApi.createGuest(
        {
          first_name: String(f.get("first_name")),
          last_name: String(f.get("last_name")),
          email: String(f.get("email") || "") || null,
          phone: String(f.get("phone") || ""),
          nationality: String(f.get("nationality") || ""),
          vip: f.get("vip") === "on",
          dietary_requirements: String(f.get("dietary_requirements") || ""),
          allergies: String(f.get("allergies") || ""),
          preferences: String(f.get("preferences") || ""),
          notes: String(f.get("notes") || ""),
          birthday: String(f.get("birthday") || "") || null,
          anniversary: String(f.get("anniversary") || "") || null,
          repeat_guest: f.get("repeat_guest") === "on",
          safari_preferences: String(f.get("safari_preferences") || ""),
        },
        actor.current,
      );
      if (!valid(version)) return;
      setOpen(false);
      await load();
    } catch (e: any) {
      if (valid(version)) {
        if (e instanceof ApiError && [401, 403, 404].includes(e.status)) {
          setRows([]);
          setSelected(null);
          setOpen(false);
        }
        setError(e.message);
      }
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  async function save() {
    if (!selected || lock.current || !valid(generation.current)) return;
    lock.current = true;
    setBusy(true);
    const version = generation.current;
    try {
      await lodgeApi.updateGuest(
        selected.id,
        {
          vip: selected.vip,
          dietary_requirements: selected.dietary_requirements,
          allergies: selected.allergies,
          preferences: selected.preferences,
          notes: selected.notes,
          birthday: selected.birthday || null,
          anniversary: selected.anniversary || null,
          repeat_guest: !!selected.repeat_guest,
          safari_preferences: selected.safari_preferences || "",
        },
        actor.current,
      );
      if (!valid(version)) return;
      setSelected(null);
      await load();
    } catch (e: any) {
      if (valid(version)) {
        if (e instanceof ApiError && [401, 403, 404].includes(e.status)) {
          setRows([]);
          setSelected(null);
          setOpen(false);
        }
        setError(e.message);
      }
    } finally {
      lock.current = false;
      if (mounted.current) setBusy(false);
    }
  }
  return (
    <>
      <div className="pageHeader">
        <div>
          <span className="eyebrow">GUEST CRM</span>
          <h1>Guests</h1>
          <p>
            Know your guests. Keep preferences, dietary needs and stay history
            close at hand.
          </p>
        </div>
        {canManage && (
          <button className="button primary" onClick={() => setOpen(true)}>
            + Guest
          </button>
        )}
      </div>
      {error && (
        <div className="panel dangerText" role="alert">
          {error}{" "}
          <button className="linkButton" onClick={() => void load()}>
            {copy.retry}
          </button>
        </div>
      )}
      {loading && <p role="status">{copy.loadingGuests}</p>}
      <div className="toolbar">
        <Field label="Search guests…">
          <input
            className="field"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Search guests…"
          />
        </Field>
      </div>
      <TableScroll as="section" className="panel tableWrap">
        <table className="dataTable">
          <thead>
            <tr>
              <th>Guest</th>
              <th>Nationality</th>
              <th>Current unit</th>
              <th>Current stay</th>
              <th>Completed stays</th>
              <th>Profile</th>
            </tr>
          </thead>
          <tbody>
            {list.map((g) => (
              <tr
                key={g.id}
                className="clickable"
                onClick={() => setSelected(g)}
              >
                <td>
                  <button className="linkButton" onClick={() => setSelected(g)}>
                    {g.name}
                  </button>
                  <br />
                  <small>{g.email || g.phone || "—"}</small>
                </td>
                <td>{g.nationality || "—"}</td>
                <td>{g.current_unit || "—"}</td>
                <td>
                  {g.stay_status ? (
                    <StatusPill value={g.stay_status} />
                  ) : (
                    <span>—</span>
                  )}
                </td>
                <td>{g.completed_stays}</td>
                <td>{g.vip ? <StatusPill value="VIP" /> : "Standard"}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!loading && !error && !list.length && (
          <div className="empty">No guest profiles found.</div>
        )}
      </TableScroll>
      {selected && (
        <Drawer onClose={() => setSelected(null)}>
          <div className="drawerHead">
            <div>
              <h1>{selected.name}</h1>
              <div className="sub">
                {selected.nationality || "Nationality not recorded"}
              </div>
            </div>
            <button
              className="closeButton"
              onClick={() => setSelected(null)}
              aria-label="Close dialog"
              type="button"
            >
              ×
            </button>
          </div>
          <Form
            onSubmit={(event) => {
              event.preventDefault();
              if (canManage && !selected.anonymized_at) return save();
            }}
          >
            <label className="label">
              <input
                type="checkbox"
                name="vip"
                disabled={!canManage || !!selected.anonymized_at}
                checked={selected.vip}
                onChange={(e) =>
                  setSelected({ ...selected, vip: e.target.checked })
                }
              />{" "}
              VIP / priority guest
            </label>
            {selected.anonymized_at && <p className="sub">{copy.anonymized}</p>}
            <div className="inlineForm">
              {(["birthday", "anniversary"] as const).map((key) => (
                <Field key={key} label={copy[key]} helper={copy.occasionsHint}>
                  <input
                    className="field"
                    name={key}
                    type="date"
                    disabled={!canManage || !!selected.anonymized_at}
                    value={selected[key] || ""}
                    onChange={(event) =>
                      setSelected({
                        ...selected,
                        [key]: event.target.value || null,
                      })
                    }
                  />
                </Field>
              ))}
            </div>
            <Field label={copy.repeat} helper={copy.repeatHint}>
              <input
                type="checkbox"
                name="repeat_guest"
                disabled={!canManage || !!selected.anonymized_at}
                checked={!!selected.repeat_guest}
                onChange={(event) =>
                  setSelected({
                    ...selected,
                    repeat_guest: event.target.checked,
                  })
                }
              />
            </Field>
            <Field label={copy.safari}>
              <textarea
                className="textarea"
                name="safari_preferences"
                disabled={!canManage || !!selected.anonymized_at}
                value={selected.safari_preferences || ""}
                maxLength={4000}
                onChange={(event) =>
                  setSelected({
                    ...selected,
                    safari_preferences: event.target.value,
                  })
                }
              />
            </Field>
            <Field label="Dietary requirements">
              <textarea
                className="textarea"
                name="dietary_requirements"
                disabled={!canManage || !!selected.anonymized_at}
                value={selected.dietary_requirements}
                onChange={(e) =>
                  setSelected({
                    ...selected,
                    dietary_requirements: e.target.value,
                  })
                }
              />
            </Field>
            <Field label="Allergies">
              <textarea
                className="textarea"
                name="allergies"
                disabled={!canManage || !!selected.anonymized_at}
                value={selected.allergies}
                onChange={(e) =>
                  setSelected({ ...selected, allergies: e.target.value })
                }
              />
            </Field>
            <Field label="Preferences">
              <textarea
                className="textarea"
                name="preferences"
                disabled={!canManage || !!selected.anonymized_at}
                value={selected.preferences}
                onChange={(e) =>
                  setSelected({ ...selected, preferences: e.target.value })
                }
              />
            </Field>
            <Field label="Internal notes">
              <textarea
                className="textarea"
                name="notes"
                disabled={!canManage || !!selected.anonymized_at}
                value={selected.notes}
                onChange={(e) =>
                  setSelected({ ...selected, notes: e.target.value })
                }
              />
            </Field>
            {canManage && !selected.anonymized_at && (
              <div className="drawerActions">
                <button className="button primary" disabled={busy}>
                  {busy ? copy.saving : "Save profile"}
                </button>
              </div>
            )}
          </Form>
          <GuestCommunications
            key={selected.id}
            guestId={selected.id}
            canManage={canManage && !selected.anonymized_at}
          />
        </Drawer>
      )}
      {open && (
        <Drawer onClose={() => setOpen(false)}>
          <div className="drawerHead">
            <div>
              <h1>Add guest</h1>
            </div>
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
            <div className="inlineForm">
              <div>
                <Field label="First name">
                  <input className="field" name="first_name" required />
                </Field>
              </div>
              <div>
                <Field label="Last name">
                  <input className="field" name="last_name" required />
                </Field>
              </div>
            </div>
            <Field label="Email">
              <input className="field" name="email" type="email" />
            </Field>
            <Field label="Phone">
              <input className="field" name="phone" />
            </Field>
            <div className="inlineForm">
              {(["birthday", "anniversary"] as const).map((key) => (
                <Field key={key} label={copy[key]} helper={copy.occasionsHint}>
                  <input className="field" name={key} type="date" />
                </Field>
              ))}
            </div>
            <Field label={copy.repeat} helper={copy.repeatHint}>
              <input type="checkbox" name="repeat_guest" />
            </Field>
            <Field label={copy.safari}>
              <textarea
                className="textarea"
                name="safari_preferences"
                maxLength={4000}
              />
            </Field>
            <Field label="Nationality">
              <CountryPicker name="nationality" />
            </Field>
            <label className="label">
              <input type="checkbox" name="vip" /> VIP / priority guest
            </label>
            <Field label="Dietary requirements">
              <textarea className="textarea" name="dietary_requirements" />
            </Field>
            <Field label="Allergies">
              <textarea className="textarea" name="allergies" />
            </Field>
            <Field label="Preferences">
              <textarea className="textarea" name="preferences" />
            </Field>
            <Field label="Internal notes">
              <textarea className="textarea" name="notes" />
            </Field>
            <div className="drawerActions">
              <button className="button primary" disabled={busy}>
                {busy ? copy.saving : "Create guest"}
              </button>
            </div>
          </Form>
        </Drawer>
      )}
    </>
  );
}
