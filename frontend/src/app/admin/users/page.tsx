"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import type { Page, Role, User } from "@/lib/types";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { Icon } from "@/components/admin/ui/Icon";
import { Modal } from "@/components/admin/ui/Modal";
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

export default function UsersAdmin() {
  const { user: me } = useAuth();
  const { push } = useToast();
  const [data, setData] = useState<Page<User> | null>(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [adding, setAdding] = useState(false);
  const [formError, setFormError] = useState("");

  const load = useCallback(async () => {
    try {
      setData(await apiFetch<Page<User>>(`/users?page_size=100${q ? `&q=${encodeURIComponent(q)}` : ""}`));
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to load users");
    }
  }, [q]);

  useEffect(() => {
    void load();
  }, [load]);

  async function update(id: number, body: Record<string, unknown>) {
    setError("");
    try {
      await apiFetch(`/users/${id}`, { method: "PATCH", body: JSON.stringify(body) });
      push({ title: "Saved" });
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
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
            onChange={(e) => update(u.id, { role: e.target.value })}
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
            onChange={(e) => update(u.id, { is_active: e.target.checked })}
            className="size-4 accent-[var(--color-accent)]"
          />
          <span className="sr-only">Account active for {u.email}</span>
          <Pill tone={u.is_active ? "success" : "neutral"}>{u.is_active ? "Active" : "Disabled"}</Pill>
        </label>
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
    </div>
  );
}
