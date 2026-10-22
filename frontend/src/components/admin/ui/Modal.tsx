"use client";

import * as Dialog from "@radix-ui/react-dialog";
import { useEffect, useState } from "react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/Button";
import { Icon } from "./Icon";

const SIZES = { sm: "max-w-md", md: "max-w-xl", lg: "max-w-3xl" } as const;

export function Modal({
  open,
  onClose,
  title,
  description,
  children,
  footer,
  size = "md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: React.ReactNode;
  footer?: React.ReactNode;
  size?: keyof typeof SIZES;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(o) => !o && onClose()}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-night/50" />
        <Dialog.Content
          className={cn(
            "fixed left-1/2 top-1/2 z-50 flex max-h-[90dvh] w-[calc(100vw-2rem)] -translate-x-1/2 -translate-y-1/2 flex-col rounded-[var(--radius-card)] bg-surface shadow-[var(--shadow-raised,0_24px_60px_-20px_rgb(0_0_0/0.5))] focus:outline-none",
            SIZES[size],
          )}
        >
          <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
            <div className="min-w-0">
              <Dialog.Title className="font-admin text-lg font-semibold text-ink">{title}</Dialog.Title>
              <Dialog.Description className={description ? "mt-0.5 text-sm text-muted" : "sr-only"}>{description ?? title}</Dialog.Description>
            </div>
            <Dialog.Close className="-mr-2 grid size-9 shrink-0 place-items-center rounded-full text-muted hover:bg-sand hover:text-ink">
              <Icon name="close" />
              <span className="sr-only">Close</span>
            </Dialog.Close>
          </div>
          <div className="overflow-y-auto px-5 py-4">{children}</div>
          {footer && <div className="flex flex-wrap justify-end gap-2 border-t border-line px-5 py-3">{footer}</div>}
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

/** A short code without look-alike characters, new each time a dialog opens. */
function randomCode(length = 5): string {
  const chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = new Uint32Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => chars[b % chars.length]).join("");
}

/**
 * "Are you sure?" for anything that can't be undone. The button names the action ("Delete coupon").
 * A delete (`confirmLabel` starting with "Delete", or `typeToConfirm`) also asks the person to type a random code first.
 */
export function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel,
  tone = "danger",
  busy,
  typeToConfirm,
  onConfirm,
  onCancel,
}: {
  open: boolean;
  title: string;
  message: React.ReactNode;
  confirmLabel: string;
  tone?: "danger" | "primary";
  busy?: boolean;
  typeToConfirm?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const needsCode = typeToConfirm ?? /^delete/i.test(confirmLabel);
  const [code, setCode] = useState("");
  const [typed, setTyped] = useState("");
  useEffect(() => {
    if (open) {
      setCode(randomCode());
      setTyped("");
    }
  }, [open]);
  const ready = !needsCode || typed.trim().toUpperCase() === code;
  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      size="sm"
      footer={
        <>
          <Button variant="secondary" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
          <Button variant={tone === "danger" ? "danger" : "primary"} onClick={onConfirm} disabled={busy || !ready}>
            {busy ? "Working…" : confirmLabel}
          </Button>
        </>
      }
    >
      <div className="text-sm text-muted">{message}</div>
      {needsCode && (
        <form
          className="mt-4"
          onSubmit={(e) => {
            e.preventDefault();
            if (ready && !busy) onConfirm();
          }}
        >
          <label htmlFor="confirm-code" className="block text-sm text-ink">
            To confirm, type <strong className="rounded bg-sand px-1.5 py-0.5 font-mono tracking-widest">{code}</strong> below
          </label>
          <input
            id="confirm-code"
            value={typed}
            onChange={(e) => setTyped(e.target.value)}
            autoComplete="off"
            autoCapitalize="characters"
            spellCheck={false}
            className="mt-2 h-10 w-full rounded-[var(--radius-control)] border border-line bg-surface px-3 font-mono uppercase tracking-widest focus-visible:border-accent"
          />
        </form>
      )}
    </Modal>
  );
}
