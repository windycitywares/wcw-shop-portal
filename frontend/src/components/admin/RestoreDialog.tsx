"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { Modal } from "@/components/admin/ui/Modal";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

interface Challenge {
  file: string;
  word: string;
  token: string;
  expires_in: number;
}

/** "When was this backup made?" from wcw-backup-20261015-030509.dump.enc (UTC in the name). */
export function backupDate(file: string): string {
  const m = /(\d{4})(\d{2})(\d{2})-(\d{2})(\d{2})(\d{2})/.exec(file);
  if (!m) return file;
  const d = new Date(Date.UTC(+m[1], +m[2] - 1, +m[3], +m[4], +m[5], +m[6]));
  return d.toLocaleString("en-US", { dateStyle: "medium", timeStyle: "short" });
}

/**
 * Restore one backup into the live database. The server issues a random word that must be typed exactly; the
 * Restore button stays disabled until it matches. A safety backup of the current data is made first.
 */
export function RestoreDialog({ file, onClose, onDone }: { file: string | null; onClose: () => void; onDone: () => void }) {
  const { push } = useToast();
  const [challenge, setChallenge] = useState<Challenge | null>(null);
  const [typed, setTyped] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    setChallenge(null);
    setTyped("");
    setError("");
    if (!file) return;
    apiFetch<Challenge>("/admin/backups/restore/prepare", { method: "POST", body: JSON.stringify({ file }) }).then(setChallenge, (e) => setError(e.message));
  }, [file]);

  const matches = !!challenge && typed.trim().toLowerCase() === challenge.word;

  async function restore() {
    if (!challenge || !matches) return;
    setBusy(true);
    setError("");
    try {
      const r = await apiFetch<{ status: "restored" | "failed"; safety_backup: string | null; error: string | null }>("/admin/backups/restore", {
        method: "POST",
        body: JSON.stringify({ file: challenge.file, word: typed, token: challenge.token }),
      });
      if (r.status === "restored") {
        push({ title: "Backup restored", description: `The shop now has the data from ${backupDate(challenge.file)}. Safety backup: ${r.safety_backup}` });
        onDone();
        onClose();
      } else {
        setError(r.error ?? "The restore didn't run. Nothing was changed.");
      }
    } catch (e) {
      setError(e instanceof Error ? e.message : "The restore didn't run. Nothing was changed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal
      open={file !== null}
      onClose={() => !busy && onClose()}
      title="Restore this backup?"
      description={file ? `Backup from ${backupDate(file)}` : undefined}
      size="sm"
      footer={
        <>
          <Button variant="secondary" size="sm" onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button size="sm" variant="danger" onClick={restore} disabled={!matches || busy}>
            {busy ? "Restoring… (keep this page open)" : "Restore backup"}
          </Button>
        </>
      }
    >
      <div className="space-y-4 text-sm">
        <Alert tone="danger">
          Everything in the live shop (orders, customers, products, settings) is replaced by this backup. Anything that happened after it was made is lost from the shop.
        </Alert>
        <ul className="list-disc space-y-1 pl-5 text-muted">
          <li>A fresh backup of the current data is made first, so you can go back.</li>
          <li>It runs as one step: if anything fails, nothing is changed.</li>
          <li>Everyone may need to sign in again afterwards.</li>
        </ul>
        {error && <Alert tone="danger">{error}</Alert>}
        {!challenge && !error ? (
          <div className="skeleton h-16" />
        ) : challenge ? (
          <div>
            <p>
              To confirm, type <strong className="select-all rounded bg-sand px-1.5 py-0.5 font-mono text-ink">{challenge.word}</strong> below.
            </p>
            <label htmlFor="restore-word" className="sr-only">
              Type {challenge.word} to confirm
            </label>
            <Input
              id="restore-word"
              value={typed}
              onChange={(e) => setTyped(e.target.value)}
              onPaste={(e) => e.preventDefault()}
              autoComplete="off"
              spellCheck={false}
              className="mt-2 font-mono"
              placeholder={challenge.word}
              disabled={busy}
            />
            <p className="mt-1 text-xs text-muted">The word changes every time and is valid for 5 minutes.</p>
          </div>
        ) : null}
      </div>
    </Modal>
  );
}
