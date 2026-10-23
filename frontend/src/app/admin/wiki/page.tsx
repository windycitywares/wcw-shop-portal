"use client";

import { useMemo, useState } from "react";
import { ADMIN_WIKI } from "@/content/adminWiki";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelBody } from "@/components/admin/ui/Panel";
import { Input } from "@/components/ui/Field";

/** Staff-only guide to using the admin and each Settings section. */
export default function AdminWiki() {
  const [q, setQ] = useState("");
  const shown = useMemo(() => {
    const t = q.trim().toLowerCase();
    if (!t) return ADMIN_WIKI;
    return ADMIN_WIKI.filter((a) => `${a.title} ${a.summary} ${a.paragraphs.join(" ")}`.toLowerCase().includes(t));
  }, [q]);

  return (
    <>
      <PageHeader title="Admin wiki" actions={<a href="/sitemap.xml" target="_blank" rel="noreferrer" className="text-sm text-muted underline hover:text-ink">View sitemap.xml</a>}
        description="How to run the shop and use each setting, in plain language. Only signed-in staff can see this." />
      <div className="grid grid-cols-[minmax(0,1fr)] gap-6 lg:grid-cols-[14rem_minmax(0,1fr)]">
        <nav aria-label="Wiki contents" className="lg:sticky lg:top-4 lg:self-start">
          <label htmlFor="wiki-search" className="mb-1.5 block text-sm font-medium text-ink">Search the wiki</label>
          <Input id="wiki-search" type="search" value={q} onChange={(e) => setQ(e.target.value)} />
          <ul className="mt-3 space-y-1 text-sm">
            {shown.map((a) => (
              <li key={a.id}>
                <a href={`#${a.id}`} className="block rounded px-2 py-1 text-muted hover:bg-line/40 hover:text-ink focus-visible:outline focus-visible:outline-2">
                  {a.title}
                </a>
              </li>
            ))}
          </ul>
        </nav>
        <div className="space-y-4">
          {shown.length === 0 && <p className="text-sm text-muted">Nothing matches “{q}”.</p>}
          {shown.map((a) => (
            <Panel key={a.id} id={a.id} className="scroll-mt-4">
              <PanelBody>
                <h2 className="text-[1.05rem] font-semibold text-ink">{a.title}</h2>
                <p className="mt-0.5 text-sm text-muted">{a.summary}</p>
                <div className="admin-prose mt-3 space-y-2 text-sm text-ink">
                  {a.paragraphs.map((p, i) => (
                    <p key={i}>{p}</p>
                  ))}
                </div>
              </PanelBody>
            </Panel>
          ))}
        </div>
      </div>
    </>
  );
}
