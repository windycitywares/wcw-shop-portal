"use client";

import { useEffect, useState } from "react";
import { apiFetch } from "@/lib/client-api";
import { crmLink } from "@/lib/crm";
import { CrmNotice } from "@/components/admin/CrmNotice";
import { dateTime, money } from "@/components/admin/charts/format";
import { DataTable, type Column } from "@/components/admin/ui/DataTable";
import { PageHeader } from "@/components/admin/ui/PageHeader";
import { Panel, PanelHeader } from "@/components/admin/ui/Panel";
import { Pill } from "@/components/admin/ui/Pill";
import { Button } from "@/components/ui/Button";
import { Alert } from "@/components/ui/misc";

interface Campaign {
  id: number;
  name: string;
  subject: string;
  segment: string;
  coupon_kind: "percent" | "fixed" | "free_shipping" | null;
  status: "draft" | "sent";
  recipients: number;
  sent_at: string | null;
  coupons_issued: number;
  coupons_redeemed: number;
  revenue: number;
}

/** Campaigns the shop sent before email moved to the CRM. New ones are written, sent and measured there. */
export default function AdminCampaigns() {
  const [rows, setRows] = useState<Campaign[] | null>(null);
  const [segments, setSegments] = useState<{ key: string; label: string }[]>([]);
  const [problem, setProblem] = useState("");

  useEffect(() => {
    apiFetch<{ items: Campaign[]; segments: { key: string; label: string }[] }>("/admin/campaigns").then(
      (d) => {
        setRows(d.items);
        setSegments(d.segments);
      },
      (e) => setProblem(e.message),
    );
  }, []);

  const label = (key: string) => segments.find((s) => s.key === key)?.label ?? key;

  const columns: Column<Campaign>[] = [
    {
      key: "name",
      header: "Campaign",
      cell: (c) => (
        <div>
          <span className="font-medium">{c.name}</span>
          <span className="block text-xs text-muted">
            {label(c.segment)} · “{c.subject}”
          </span>
        </div>
      ),
    },
    {
      key: "status",
      header: "Status",
      cell: (c) => (c.status === "sent" ? <Pill tone="success">Sent {c.sent_at ? dateTime(c.sent_at) : ""}</Pill> : <Pill tone="neutral">Draft</Pill>),
    },
    {
      key: "results",
      header: "Results",
      align: "right",
      cell: (c) =>
        c.status === "sent" ? (
          <span className="num text-sm">
            {c.recipients} sent
            {c.coupon_kind && (
              <span className="block text-xs text-muted">
                {c.coupons_redeemed} of {c.coupons_issued} codes used · {money(c.revenue)}
              </span>
            )}
          </span>
        ) : (
          <span className="text-sm text-muted">—</span>
        ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Email campaigns"
        description="The campaigns sent from the shop, for reference."
        actions={
          <a href={crmLink("/campaigns")} target="_blank" rel="noopener noreferrer">
            <Button size="sm" tabIndex={-1}>
              Open campaigns in the CRM<span className="sr-only"> (new tab)</span>
            </Button>
          </a>
        }
      />
      <CrmNotice what="Email campaigns" path="/campaigns" action="Write, send and track campaigns in the CRM" />
      {problem && (
        <Alert tone="danger" className="mb-4">
          {problem}
        </Alert>
      )}
      <Panel>
        <PanelHeader title="Campaigns" />
        <DataTable columns={columns} rows={rows} rowKey={(c) => c.id} caption="Email campaigns" empty="No campaigns were sent from the shop." />
      </Panel>
    </div>
  );
}
