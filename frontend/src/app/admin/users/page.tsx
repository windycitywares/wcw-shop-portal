"use client";

import { useCallback, useEffect, useState } from "react";
import { useAuth } from "@/lib/auth";
import { apiFetch } from "@/lib/client-api";
import type { Page, Role, User } from "@/lib/types";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Alert } from "@/components/ui/misc";

const ROLES: Role[] = ["admin", "publisher", "author", "customer"];

export default function UsersAdmin() {
  const { user: me } = useAuth();
  const [data, setData] = useState<Page<User> | null>(null);
  const [q, setQ] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

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
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Update failed");
    }
  }

  async function onCreate(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = e.currentTarget;
    const fd = new FormData(form);
    setError("");
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
      setNotice("Account created. Share the password with them securely; they can sign in right away.");
      await load();
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not create account");
    }
  }

  return (
    <div>
      <h1 className="text-4xl">Users</h1>
      <p className="mt-2 text-sm text-muted">
        Admins manage everything · Publishers review and publish · Authors draft products · Customers shop.
      </p>
      {error && <Alert tone="danger" className="mt-4">{error}</Alert>}
      {notice && <Alert tone="success" className="mt-4">{notice}</Alert>}

      <form
        className="mt-6 flex gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          setQ(String(new FormData(e.currentTarget).get("q") || ""));
        }}
      >
        <label htmlFor="user-q" className="sr-only">
          Search users
        </label>
        <Input id="user-q" name="q" placeholder="Name or email" className="max-w-xs" />
        <Button type="submit" variant="secondary">
          Search
        </Button>
      </form>

      <div className="mt-4 overflow-x-auto rounded-[var(--radius-card)] border border-line bg-surface">
        <table className="w-full text-left text-sm">
          <caption className="sr-only">User accounts</caption>
          <thead className="border-b border-line text-xs uppercase tracking-wide text-muted">
            <tr>
              <th scope="col" className="px-4 py-3">User</th>
              <th scope="col" className="px-4 py-3">Role</th>
              <th scope="col" className="px-4 py-3">Active</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {data?.items.map((u) => {
              const self = u.id === me?.id;
              return (
                <tr key={u.id}>
                  <td className="px-4 py-3">
                    {u.full_name || "—"}
                    <span className="block text-xs text-muted">{u.email}</span>
                  </td>
                  <td className="px-4 py-3">
                    <label htmlFor={`role-${u.id}`} className="sr-only">
                      Role for {u.email}
                    </label>
                    <Select
                      id={`role-${u.id}`}
                      value={u.role}
                      disabled={self}
                      onChange={(e) => update(u.id, { role: e.target.value })}
                      className="w-36 capitalize"
                    >
                      {ROLES.map((r) => (
                        <option key={r} value={r}>
                          {r}
                        </option>
                      ))}
                    </Select>
                  </td>
                  <td className="px-4 py-3">
                    <label className="flex items-center gap-2">
                      <input
                        type="checkbox"
                        checked={u.is_active}
                        disabled={self}
                        onChange={(e) => update(u.id, { is_active: e.target.checked })}
                        className="size-4"
                      />
                      <span className="sr-only">Account active for {u.email}</span>
                    </label>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      <form onSubmit={onCreate} className="mt-8 max-w-2xl space-y-4 rounded-[var(--radius-card)] border border-line bg-surface p-5">
        <h2 className="text-2xl">Add a team member</h2>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Name">{(p) => <Input {...p} name="full_name" />}</Field>
          <Field label="Email">{(p) => <Input {...p} name="email" type="email" required />}</Field>
          <Field label="Temporary password" hint="At least 8 characters.">
            {(p) => <Input {...p} name="password" type="password" minLength={8} required autoComplete="new-password" />}
          </Field>
          <Field label="Role">
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
        <Button type="submit">Create account</Button>
      </form>
    </div>
  );
}
