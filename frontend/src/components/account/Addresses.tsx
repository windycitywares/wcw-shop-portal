"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useI18n } from "@/i18n/client";
import { addressesApi, COUNTRIES, countryName, type Address, type AddressInput } from "@/lib/account";
import { Button } from "@/components/ui/Button";
import { Field, Input, Select } from "@/components/ui/Field";
import { Alert, Badge } from "@/components/ui/misc";

type Editing = { mode: "new" } | { mode: "edit"; address: Address } | null;

export function Addresses() {
  const { t, locale } = useI18n();
  const [items, setItems] = useState<Address[] | null>(null);
  const [editing, setEditing] = useState<Editing>(null);
  const [confirming, setConfirming] = useState<number | null>(null);
  const [notice, setNotice] = useState<{ tone: "success" | "danger"; text: string } | null>(null);
  const headingRef = useRef<HTMLHeadingElement>(null);

  const load = useCallback(async () => {
    try {
      setItems(await addressesApi.list());
    } catch (err) {
      setItems([]);
      setNotice({ tone: "danger", text: err instanceof Error ? err.message : t.auth.error });
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function act(fn: () => Promise<unknown>, success?: string) {
    setNotice(null);
    try {
      await fn();
      await load();
      if (success) setNotice({ tone: "success", text: success });
      return true;
    } catch (err) {
      setNotice({ tone: "danger", text: err instanceof Error ? err.message : t.auth.error });
      return false;
    }
  }

  return (
    <section aria-labelledby="addresses-heading" className="mt-6 rounded-[var(--radius-card)] border border-line bg-surface p-6">
      <div className="flex flex-wrap items-baseline justify-between gap-3">
        <h2 id="addresses-heading" ref={headingRef} tabIndex={-1} className="text-2xl">
          {t.addresses.title}
        </h2>
        {!editing && items && (
          <Button size="sm" variant="secondary" onClick={() => setEditing({ mode: "new" })}>
            {t.addresses.add}
          </Button>
        )}
      </div>
      <p className="mt-2 text-sm text-muted">{t.addresses.intro}</p>
      <div aria-live="polite" className="mt-4 empty:hidden">
        {notice && <Alert tone={notice.tone}>{notice.text}</Alert>}
      </div>

      {editing && (
        <AddressForm
          key={editing.mode === "edit" ? editing.address.id : "new"}
          initial={editing.mode === "edit" ? editing.address : null}
          isFirst={!items?.length}
          onCancel={() => {
            setEditing(null);
            headingRef.current?.focus();
          }}
          onSave={async (data) => {
            const ok = await act(
              () => (editing.mode === "edit" ? addressesApi.update(editing.address.id, data) : addressesApi.create(data)),
              t.addresses.saved,
            );
            if (ok) {
              setEditing(null);
              headingRef.current?.focus();
            }
          }}
        />
      )}

      {items === null ? (
        <p className="mt-4 text-sm text-muted">{t.account.loading}</p>
      ) : items.length === 0 && !editing ? (
        <p className="mt-4 text-sm text-muted">{t.addresses.empty}</p>
      ) : (
        <ul className="mt-5 grid gap-4 sm:grid-cols-2">
          {items.map((a) => (
            <li key={a.id} className="flex flex-col rounded-[var(--radius-card)] border border-line p-4 text-sm">
              <div className="flex items-center gap-2">
                <p className="font-semibold">{a.label || a.full_name}</p>
                {a.is_default && <Badge tone="accent">{t.addresses.isDefault}</Badge>}
              </div>
              <address className="mt-2 not-italic leading-relaxed text-muted">
                {a.label && <>{a.full_name}<br /></>}
                {a.company && <>{a.company}<br /></>}
                {a.line1}
                {a.line2 && <>, {a.line2}</>}
                <br />
                {a.city}
                {a.region && <>, {a.region}</>} {a.postal_code}
                <br />
                {countryName(a.country, locale)}
                {a.phone && <><br />{a.phone}</>}
              </address>
              <div className="mt-auto flex flex-wrap gap-x-4 gap-y-2 pt-4">
                {confirming === a.id ? (
                  <>
                    <span className="font-medium">{t.addresses.confirmRemove}</span>
                    <button
                      type="button"
                      className="font-medium text-danger underline"
                      onClick={async () => {
                        setConfirming(null);
                        await act(() => addressesApi.remove(a.id), t.addresses.removed);
                        headingRef.current?.focus();
                      }}
                    >
                      {t.addresses.yesRemove}
                    </button>
                    <button type="button" className="underline" onClick={() => setConfirming(null)}>
                      {t.addresses.cancel}
                    </button>
                  </>
                ) : (
                  <>
                    <button type="button" className="text-accent underline" onClick={() => setEditing({ mode: "edit", address: a })}>
                      {t.addresses.edit}
                      <span className="sr-only">: {a.label || a.full_name}</span>
                    </button>
                    {!a.is_default && (
                      <button type="button" className="text-accent underline" onClick={() => act(() => addressesApi.makeDefault(a.id))}>
                        {t.addresses.makeDefault}
                        <span className="sr-only">: {a.label || a.full_name}</span>
                      </button>
                    )}
                    <button type="button" className="text-muted underline" onClick={() => setConfirming(a.id)}>
                      {t.addresses.remove}
                      <span className="sr-only">: {a.label || a.full_name}</span>
                    </button>
                  </>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function AddressForm({
  initial,
  isFirst,
  onSave,
  onCancel,
}: {
  initial: Address | null;
  isFirst: boolean;
  onSave: (data: AddressInput) => Promise<void>;
  onCancel: () => void;
}) {
  const { t, locale } = useI18n();
  const [busy, setBusy] = useState(false);
  const firstField = useRef<HTMLInputElement>(null);
  useEffect(() => firstField.current?.focus(), []);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const fd = new FormData(e.currentTarget);
    const s = (k: string) => String(fd.get(k) ?? "").trim() || null;
    setBusy(true);
    await onSave({
      label: s("label"),
      full_name: s("full_name") ?? "",
      company: s("company"),
      line1: s("line1") ?? "",
      line2: s("line2"),
      city: s("city") ?? "",
      region: s("region"),
      postal_code: s("postal_code") ?? "",
      country: s("country") ?? "US",
      phone: s("phone"),
      is_default: isFirst || fd.get("is_default") === "on",
    });
    setBusy(false);
  }

  const opt = (label: string) => `${label} ${t.addresses.optional}`;
  const v = initial;
  return (
    <form onSubmit={submit} className="mt-5 space-y-4 rounded-[var(--radius-card)] border border-line bg-canvas p-5">
      <h3 className="text-xl">{initial ? t.addresses.editTitle : t.addresses.addTitle}</h3>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t.addresses.fullName}>
          {(p) => <Input {...p} ref={firstField} name="full_name" required maxLength={200} autoComplete="shipping name" defaultValue={v?.full_name ?? ""} />}
        </Field>
        <Field label={opt(t.addresses.label)} hint={t.addresses.labelHint}>
          {(p) => <Input {...p} name="label" maxLength={50} defaultValue={v?.label ?? ""} />}
        </Field>
      </div>
      <Field label={opt(t.addresses.company)}>
        {(p) => <Input {...p} name="company" maxLength={200} autoComplete="shipping organization" defaultValue={v?.company ?? ""} />}
      </Field>
      <Field label={t.addresses.line1}>
        {(p) => <Input {...p} name="line1" required maxLength={200} autoComplete="shipping address-line1" defaultValue={v?.line1 ?? ""} />}
      </Field>
      <Field label={opt(t.addresses.line2)}>
        {(p) => <Input {...p} name="line2" maxLength={200} autoComplete="shipping address-line2" defaultValue={v?.line2 ?? ""} />}
      </Field>
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label={t.addresses.city}>
          {(p) => <Input {...p} name="city" required maxLength={100} autoComplete="shipping address-level2" defaultValue={v?.city ?? ""} />}
        </Field>
        <Field label={opt(t.addresses.region)}>
          {(p) => <Input {...p} name="region" maxLength={100} autoComplete="shipping address-level1" defaultValue={v?.region ?? ""} />}
        </Field>
        <Field label={t.addresses.postalCode}>
          {(p) => <Input {...p} name="postal_code" required maxLength={20} autoComplete="shipping postal-code" defaultValue={v?.postal_code ?? ""} />}
        </Field>
      </div>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label={t.addresses.country}>
          {(p) => (
            <Select {...p} name="country" autoComplete="shipping country" defaultValue={v?.country ?? "US"}>
              {COUNTRIES.map((c) => (
                <option key={c} value={c}>
                  {countryName(c, locale)}
                </option>
              ))}
            </Select>
          )}
        </Field>
        <Field label={opt(t.addresses.phone)} hint={t.addresses.phoneHint}>
          {(p) => <Input {...p} name="phone" type="tel" maxLength={40} autoComplete="shipping tel" defaultValue={v?.phone ?? ""} />}
        </Field>
      </div>
      {!isFirst && !v?.is_default && (
        <label className="flex items-center gap-2 text-sm">
          <input type="checkbox" name="is_default" className="h-4 w-4 accent-[var(--color-accent)]" />
          {t.addresses.setDefault}
        </label>
      )}
      <div className="flex gap-3">
        <Button type="submit" disabled={busy}>
          {busy ? t.addresses.saving : t.addresses.save}
        </Button>
        <Button type="button" variant="ghost" onClick={onCancel}>
          {t.addresses.cancel}
        </Button>
      </div>
    </form>
  );
}
