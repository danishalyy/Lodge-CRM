"use client";
import * as Dialog from "@radix-ui/react-dialog";
import { Button } from "./button";
export function ConfirmDialog({
  open,
  onOpenChange,
  title,
  description,
  onConfirm,
  actionLabel = "Confirm removal",
}: {
  actionLabel?: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description: string;
  onConfirm: () => void;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={onOpenChange}>
      <Dialog.Portal>
        <Dialog.Overlay className="glassOverlay" />
        <Dialog.Content className="glassDialog confirmationDialog">
          <Dialog.Title>{title}</Dialog.Title>
          <Dialog.Description>{description}</Dialog.Description>
          <div className="drawerActions">
            <Button variant="secondary" onClick={() => onOpenChange(false)}>
              Cancel
            </Button>
            <Button
              variant="destructive"
              onClick={() => {
                onOpenChange(false);
                onConfirm();
              }}
            >
              {actionLabel}
            </Button>
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}
