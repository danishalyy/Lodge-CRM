"use client";
import { Command } from "cmdk";
import { useRouter } from "next/navigation";
import UiIcon, { moduleIcon } from "./UiIcon";
export default function WorkspaceCommand({
  open,
  onClose,
  items,
}: {
  open: boolean;
  onClose: () => void;
  items: readonly (readonly string[])[];
}) {
  const router = useRouter();
  return (
    <Command.Dialog
      open={open}
      onOpenChange={(v) => {
        if (!v) onClose();
      }}
      label="Search workspace"
      className="commandPalette"
    >
      <Command.Input
        placeholder="Search modules…"
        aria-label="Search modules"
      />
      <Command.List>
        <Command.Empty>No matching module.</Command.Empty>
        <Command.Group heading="Workspace">
          {items.map(([key, label]) => (
            <Command.Item
              key={key}
              value={label}
              onSelect={() => {
                onClose();
                router.push("/" + key);
              }}
            >
              <UiIcon name={moduleIcon(key)} />
              <span>{label}</span>
            </Command.Item>
          ))}
        </Command.Group>
      </Command.List>
    </Command.Dialog>
  );
}
