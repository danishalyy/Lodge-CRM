"use client";
import { Check, Minus } from "lucide-react";
import { TableScroll } from "./table-scroll";
import { accessCopy as c } from "@/lib/strings/access";
export function PermissionMatrix({
  groups,
  level,
  onChange,
}: {
  groups: any[];
  level: (group: any) => string;
  onChange: (group: any, value: string) => void;
}) {
  return (
    <TableScroll className="tableWrap permissionMatrix">
      <table className="dataTable">
        <thead>
          <tr>
            <th>{c.scope}</th>
            <th>{c.no}</th>
            <th>{c.view}</th>
            <th>{c.editAccess}</th>
          </tr>
        </thead>
        <tbody>
          {groups.map((group) => (
            <tr key={group.key}>
              <td>{group.name}</td>
              {["none", "view", "edit"].map((value) => {
                const selected = level(group) === value,
                  available =
                    value === "none" ||
                    group.permissions.some(
                      (p: any) =>
                        p.can_grant &&
                        p.level === (value === "view" ? "view" : "edit"),
                    );
                return (
                  <td key={value}>
                    <button
                      type="button"
                      className={
                        "permissionToggle" + (selected ? " selected" : "")
                      }
                      aria-label={`${group.name}: ${value === "none" ? c.no : value === "view" ? c.view : c.editAccess}`}
                      aria-pressed={selected}
                      disabled={!available}
                      onClick={() => onChange(group, value)}
                    >
                      {selected ? <Check size={16} /> : <Minus size={14} />}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </TableScroll>
  );
}
