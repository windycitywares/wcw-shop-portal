"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { API_URL, apiFetch } from "@/lib/client-api";
import type { Page, Role, User } from "@/lib/types";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Icon } from "@/components/admin/ui/Icon";
import { ConfirmDialog, Modal } from "@/components/admin/ui/Modal";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { useToast } from "@/components/admin/ui/Toast";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

const ROLES: Role[] = ["admin", "publisher", "author", "customer"];
const ROLE_HELP: Record<Role, string> = {
  admin: "Manages everything, including team accounts.",
  publisher: "Reviews and publishes products.",
  author: "Drafts and edits their own products.",
  customer: "Shops, and sees their own orders and addresses.",
};

/** A change waiting for "are you sure?": a new role, or switching the account on or off. */
type Pending = { user: User; role: Role } | { user: User; active: boolean };

const who = (u: User) => u.full_name || u.email;

/** A readable temporary password (no look-alike characters) the admin can pass on. */
function suggestPassword(length = 14): string {
  const chars = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789";
  const bytes = new Uint32Array(length);
  crypto.getRandomValues(bytes);
  return Array.from(bytes, (b) => chars[b % chars.length]).join("");
}

export default function UsersAdmin() {
  const { user: me } = useAuth();
  const { push } = useToast();
  const [data, setData] = useState<Page<User> | null>(null);
  const [q, setQ] = useState("");
  const [view, setView] = useState<"team" | "customers">("team");
  const [page, setPage] = useState(1);
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [formError, setFormError] = useState("");
  const [pending, setPending] = useState<Pending | null>(null);
  const [saving, setSaving] = useState(false);
  const [resetting, setResetting] = useState<User | null>(null);
  const [editing, setEditing] = useState<User | null>(null);
  const [editName, setEditName] = useState("");
  const [editEmail, setEditEmail] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [testMode, setTestMode] = useState(false);

  const load = useCallback(async () => {
    try {
      const params = new URLSearchParams();
      params.set("page_size", "25");
      params.set("page", String(page));
      if (q) params.set("q", q);
      if (view === "team") params.set("staff", "true");
      else params.set("staff", "false");
      setData(await apiFetch<Page<User>>(`/users?${params.toString()}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load users");
    }
  }, [q, view, page]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    setPage(1);
  }, [q, view]);

  // In Test mode a new password only changes the test copy of the account; say so in the dialog.
  useEffect(() => {
    fetch(`${API_URL}/environment`, { cache: "no-store" })
      .then((r) => (r.ok ? r.json() : { test: false }))
      .then((d: { test?: boolean }) => setTestMode(Boolean(d.test)))
      .catch(() => undefined);
  }, []);

  function openReset(u: User) {
    setNewPassword(suggestPassword());
    setResetting(u);
  }

  function openEdit(u: User) {
    setEditName(u.full_name ?? "");
    setEditEmail(u.email);
    setEditing(u);
  }

  async function saveEdit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!editing) return;
    setSaving(true);
    setError("");
    try {
      await apiFetch(`/users/${editing.id}`, {
        method: "PATCH",
        body: JSON.stringify({ full_name: editName.trim() || null, email: editEmail.trim() }),
      });
      push({ title: "Account updated", description: who(editing) });
      setEditing(null);
      await load();
    } catch (err) {
      push({ title: "Not updated", description: err instanceof Error ? err.message : undefined, tone: "danger" });
    } finally {
      setSaving(false);
    }
  }

  async function setPassword(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!resetting) return;
    setSaving(true);
    try {
      await apiFetch(`/users/${resetting.id}`, { method: "PATCH", body: JSON.stringify({ password: newPassword }) });
      push({ title: "Password set", description: `Share it with ${who(resetting)} securely. They're signed out on other devices.` });
      setResetting(null);
    } catch (err) {
      push({ title: "Password not set", description: err instanceof Error ? err.message : undefined, tone: "danger" });
    } finally {
      setSaving(false);
    }
  }

  /** Save the confirmed change, then reload the list so every row shows what the server now has. */
  async function confirmPending() {
    if (!pending) return;
    const { user } = pending;
    const body = "role" in pending ? { role: pending.role } : { is_active: pending.active };
    setSaving(true);
    setError("");
    try {
      await apiFetch(`/users/${user.id}`, { method: "PATCH", body: JSON.stringify(body) });
      if ("role" in pending) {
        push({ title: "Role changed", description: `${who(user)} is now ${pending.role === "admin" ? "an" : "a"} ${pending.role}.` });
      } else {
        push({ title: pending.active ? "Account switched on" : "Account switched off", description: who(user) });
      }
      setPending(null);
      await load();
    } catch (e) {
      push({ title: "Not changed", description: e instanceof Error ? e.message : undefined, tone: "danger" });
    } finally {
      setSaving(false);
    }
  }

  async function onCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    setFormError("");
    try {
      await apiFetch("/users", {
        method: "POST",
        body: JSON.stringify({
          email: fd.get("email"),
          password: fd.get("password"),
          full_name: fd.get("full_name") || null,
          role: fd.get("role"),
        }),
      });
      form.reset();
      setAdding(false);
      push({ title: "Account created", description: "Share the password with them securely. They can sign in right away." });
      await load();
    } catch (err) {
      setFormError(err instanceof Error ? err.message : "Could not create account");
    }
  }

  const columns: Column<User>[] = [
    {
      key: "user",
      header: "Person",
      cell: (u) => (
        <div className="flex items-center gap-3">
          <span aria-hidden="true" className="grid size-8 shrink-0 place-items-center rounded-full bg-accent-soft text-xs font-semibold text-accent-strong">
            {(u.full_name || u.email).slice(0, 1).toUpperCase()}
          </span>
          <div className="min-w-0">
            <p className="truncate font-medium">
              {u.full_name || "No name yet"}
              {u.id === me?.id && <span className="ml-2 text-xs font-normal text-muted">You</span>}
            </p>
            <p className="truncate text-xs text-muted">{u.email}</p>
          </div>
        </div>
      ),
    },
    {
      key: "role",
      header: "Role",
      cell: (u) => (
        <>
          <label htmlFor={`role-${u.id}`} className="sr-only">
            Role for {u.email}
          </label>
          <Select
            id={`role-${u.id}`}
            value={u.role}
            disabled={u.id === me?.id}
            onChange={(e) => {
              const role = e.target.value as Role;
              if (role !== u.role) setPending({ user: u, role });
            }}
            className="h-8 w-36 py-0 capitalize"
          >
            {ROLES.map((r) => (
              <option key={r} value={r}>
                {r}
              </option>
            ))}
          </Select>
        </>
      ),
    },
    {
      key: "active",
      header: "Account",
      cell: (u) => (
        <label className="inline-flex items-center gap-2">
          <input
            type="checkbox"
            checked={u.is_active}
            disabled={u.id === me?.id}
            onChange={(e) => setPending({ user: u, active: e.target.checked })}
            className="size-4 accent-[var(--color-accent)]"
          />
          <span className="sr-only">Account active for {u.email}</span>
          <Pill tone={u.is_active ? "success" : "neutral"}>{u.is_active ? "Active" : "Disabled"}</Pill>
        </label>
      ),
    },
    {
      key: "edit",
      header: "",
      cell: (u) => (
        <Button size="sm" variant="ghost" className="h-8" onClick={() => openEdit(u)}>
          Edit
          <span className="sr-only"> {u.email}</span>
        </Button>
      ),
    },
    {
      key: "password",
      header: "Password",
      cell: (u) =>
        u.id === me?.id ? (
          <span className="text-xs text-muted">In Your account</span>
        ) : (
          <Button size="sm" variant="secondary" className="h-8" onClick={() => openReset(u)}>
            Set password
            <span className="sr-only"> for {u.email}</span>
          </Button>
        ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Team and customers"
        description="Change a person's role or switch their account off. Roles decide what each person can do in this admin."
        actions={
          <Button size="sm" className="h-9" onClick={() => setAdding(true)}>
            <Icon name="plus" className="size-4" />
            Add team member
          </Button>
        }
      />
      {error && (
        <Alert tone="danger" className="mb-4">
          {error}
        </Alert>
      )}

      <div className="mb-4 flex gap-1 rounded-[var(--radius-control)] border border-line bg-surface p-1">
        {(["team", "customers"] as const).map((v) => (
          <button
            key={v}
            type="button"
            onClick={() => setView(v)}
            className={`rounded-[var(--radius-control)] px-3 py-1.5 text-sm font-medium capitalize ${view === v ? "bg-canvas text-ink" : "text-muted hover:text-ink"}`}
          >
            {v === "team" ? "Team" : "Customers"}
          </button>
        ))}
      </div>

      <Panel>
        <form
          role="search"
          className="flex items-center gap-2 border-b border-line px-4 py-3"
          onSubmit={(e) => {
            e.preventDefault();
            setQ(String(new FormData(e.currentTarget).get("q") || "").trim());
          }}
        >
          <label htmlFor="user-q" className="sr-only">
            Search people
          </label>
          <div className="relative">
            <Icon name="search" className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <input
              id="user-q"
              name="q"
              type="search"
              placeholder="Name or email"
              className="h-8 w-60 rounded-[var(--radius-control)] border border-line bg-surface pl-8 pr-2 text-sm placeholder:text-muted/70 focus-visible:border-accent"
            />
          </div>
          <Button type="submit" variant="secondary" size="sm" className="h-8">
            Search
          </Button>
        </form>
        <DataTable caption="Accounts" columns={columns} rows={data ? data.items : null} rowKey={(u) => u.id} empty="No one matches that search." />
        {data && data.total > data.page_size && (
          <div className="flex items-center justify-between border-t border-line px-4 py-3 text-sm">
            <span className="text-muted">
              {(data.page - 1) * data.page_size + 1}–{Math.min(data.page * data.page_size, data.total)} of {data.total}
            </span>
            <div className="flex gap-2">
              <Button size="sm" variant="secondary" className="h-8" disabled={data.page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>
                Previous
              </Button>
              <Button size="sm" variant="secondary" className="h-8" disabled={data.page * data.page_size >= data.total} onClick={() => setPage((p) => p + 1)}>
                Next
              </Button>
            </div>
          </div>
        )}
      </Panel>

      <Modal
        open={adding}
        onClose={() => setAdding(false)}
        title="Add a team member"
        description="They can sign in as soon as the account exists."
        footer={
          <>
            <Button variant="ghost" size="sm" className="h-9" onClick={() => setAdding(false)}>
              Cancel
            </Button>
            <Button type="submit" form="new-user-form" size="sm" className="h-9">
              Create account
            </Button>
          </>
        }
      >
        <form id="new-user-form" onSubmit={onCreate} className="space-y-4">
          {formError && <Alert tone="danger">{formError}</Alert>}
          <div className="grid gap-4 sm:grid-cols-2">
            <Field label="Name">{(p) => <Input {...p} name="full_name" />}</Field>
            <Field label="Email">{(p) => <Input {...p} name="email" type="email" required />}</Field>
            <Field label="Temporary password" hint="At least 8 characters.">
              {(p) => <Input {...p} name="password" type="password" minLength={8} required autoComplete="new-password" />}
            </Field>
            <Field label="Role" hint="Authors can draft; publishers can also publish.">
              {(p) => (
                <Select {...p} name="role" defaultValue="author" className="capitalize">
                  {ROLES.map((r) => (
                    <option key={r} value={r}>
                      {r}
                    </option>
                  ))}
                </Select>
              )}
            </Field>
          </div>
          <dl className="space-y-1 rounded-[var(--radius-control)] bg-canvas p-3 text-sm">
            {ROLES.map((r) => (
              <div key={r} className="flex gap-2">
                <dt className="w-20 shrink-0 font-medium capitalize">{r}</dt>
                <dd className="text-muted">{ROLE_HELP[r]}</dd>
              </div>
            ))}
          </dl>
        </form>
      </Modal>
      <Modal
        open={!!resetting}
        onClose={() => setResetting(null)}
        title="Set a new password"
        description={resetting ? `For ${who(resetting)} (${resetting.email}), e.g. when they've lost theirs.` : undefined}
        footer={
          <>
            <Button variant="ghost" size="sm" className="h-9" onClick={() => setResetting(null)}>
              Cancel
            </Button>
            <Button type="submit" form="set-password-form" size="sm" className="h-9" disabled={saving || newPassword.length < 8}>
              {saving ? "Setting…" : "Set password"}
            </Button>
          </>
        }
      >
        <form id="set-password-form" onSubmit={setPassword} className="space-y-4">
          {testMode && (
            <Alert tone="danger">
              Test mode is on: this changes the password in the test copy only. To change the real account, switch back to live data first (Admin → Test mode).
            </Alert>
          )}
          <Field label="New password" hint="At least 8 characters. Copy it now and share it securely; they can change it in Your account → Password.">
            {(p) => (
              <div className="flex gap-2">
                <Input
                  {...p}
                  name="new-password"
                  type="text"
                  autoComplete="new-password"
                  spellCheck={false}
                  minLength={8}
                  maxLength={72}
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="font-mono"
                />
                <Button type="button" variant="secondary" size="sm" className="h-11 shrink-0" onClick={() => setNewPassword(suggestPassword())}>
                  New suggestion
                </Button>
              </div>
            )}
          </Field>
          <p className="text-sm text-muted">They are signed out on every device and sign in again with this password.</p>
        </form>
      </Modal>

      <Modal
        open={!!editing}
        onClose={() => setEditing(null)}
        title="Edit account"
        description={editing ? `Name and email for ${who(editing)}.` : undefined}
        footer={
          <>
            <Button variant="ghost" size="sm" className="h-9" onClick={() => setEditing(null)}>
              Cancel
            </Button>
            <Button type="submit" form="edit-user-form" size="sm" className="h-9" disabled={saving}>
              {saving ? "Saving…" : "Save"}
            </Button>
          </>
        }
      >
        <form id="edit-user-form" onSubmit={saveEdit} className="space-y-4">
          <Field label="Name">
            {(p) => <Input {...p} value={editName} onChange={(e) => setEditName(e.target.value)} />}
          </Field>
          <Field label="Email">
            {(p) => <Input {...p} type="email" value={editEmail} onChange={(e) => setEditEmail(e.target.value)} required />}
          </Field>
        </form>
      </Modal>

      <ConfirmDialog
        open={!!pending}
        title={pending && "role" in pending ? "Change role?" : pending && "active" in pending && !pending.active ? "Switch this account off?" : "Switch this account on?"}
        tone={pending && "role" in pending && (pending.role === "admin" || pending.user.role === "admin") ? "danger" : pending && "active" in pending && !pending.active ? "danger" : "primary"}
        confirmLabel={pending && "role" in pending ? `Make ${pending.role}` : pending && "active" in pending && !pending.active ? "Switch off" : "Switch on"}
        busy={saving}
        onCancel={() => setPending(null)}
        onConfirm={() => void confirmPending()}
        message={
          pending &&
          ("role" in pending ? (
            <div className="space-y-2">
              <p>
                Change <strong className="text-ink">{who(pending.user)}</strong> ({pending.user.email}) from{" "}
                <strong className="capitalize text-ink">{pending.user.role}</strong> to <strong className="capitalize text-ink">{pending.role}</strong>?
              </p>
              <p>
                <span className="capitalize">{pending.role}</span>: {ROLE_HELP[pending.role]}
              </p>
              <p>It applies straight away. If they are signed in, their admin menu changes the next time they open a page.</p>
            </div>
          ) : pending.active ? (
            <p>
              <strong className="text-ink">{who(pending.user)}</strong> ({pending.user.email}) can sign in again with their password.
            </p>
          ) : (
            <p>
              <strong className="text-ink">{who(pending.user)}</strong> ({pending.user.email}) is signed out everywhere and can&apos;t sign in until you switch the
              account back on. Their orders and details are kept.
            </p>
          ))
        }
      />
    </div>
  );
}
