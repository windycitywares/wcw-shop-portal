# Admin: design system and how to extend it

The admin lives in `frontend/src/app/admin/` (pages) and `frontend/src/components/admin/` (shell, kit, charts).
Pages are client components that call the API with `apiFetch`. Nothing here needs a new dependency.

## Look and feel

- Dark sidebar (`bg-night`, always dark, whatever the theme) with a gold marker on the current page; a light
  work area; plain white panels with a 4px radius. Headings are the sans face, sentence case, no all-caps labels.
- The five storefront themes apply to the admin too (`html[data-theme]`). Use the tokens (`bg-surface`,
  `text-muted`, `text-accent`, `bg-sand`, `border-line`, `text-warning`…), never hex values, so every theme works.
- Numbers use `.num` (tabular figures) so columns line up. Money and dates come from `charts/format.ts`.
- Writing: name things the way the shop owner does ("Orders", "Coupons"), buttons say what happens
  ("Save changes", "Delete coupon"), and the toast repeats the verb ("Saved", "Coupon deleted").
  Errors say what went wrong and what to do. Empty states point to the next action.

## Building a page

```tsx
<PageHeader title="Coupons" description="…" actions={<Button>New coupon</Button>} />
<Panel>
  <PanelHeader title="Active" />
  <DataTable columns={…} rows={rows /* null while loading */} rowKey={…} caption="Coupons" empty="No coupons yet." />
  <Pagination page={page} pageSize={25} total={total} onPage={setPage} />
</Panel>
```

| Piece | File (`components/admin/…`) | Use for |
|---|---|---|
| `PageHeader`, `Panel`, `PanelHeader` | `ui/` | page frame and white surfaces |
| `MetricStrip` | `ui/Metric.tsx` | the row of headline numbers, with change vs the previous period |
| `DataTable`, `Pagination`, `Tabs`, `Pill` | `ui/` | lists, filters, status labels |
| `Modal`, `ConfirmDialog` | `ui/Modal.tsx` | forms in a dialog; "are you sure?" for anything that can't be undone |
| `useToast().push({ title })` | `ui/Toast.tsx` | confirmations |
| `DateRangePicker`, `useDateRange` | `ui/` | report pages; the range is remembered per tab |
| `LineChart`, `ColumnChart`, `BarList`, `Funnel`, `Heatmap`, `Sparkline` | `charts/` | all charts (inline SVG) |
| `ChartFrame` | `charts/ChartFrame.tsx` | title, legend and "Show as table" around any chart |

Add the page to `components/admin/nav.ts` and to `e2e/tests/admin-routes.ts`; the browser tests then open it,
scan it for accessibility problems, check it fits a phone and take screenshots without further work.

## Charts

SVG only. Single-series charts use `--color-accent`; multi-series charts take their colours in order from
`--viz-1…8` (see `globals.css`; the set was checked for colour-blind separation and has a dark-theme variant).
Never use more than eight series; fold the rest into "Other". Every chart has a crosshair and tooltip, can be
read with the arrow keys, and has a "Show as table" switch. Don't use two y-axes. Status colours
(`success`, `warning`, `danger`) always come with words or an icon, never colour alone.

## Tests

`e2e/` holds Playwright tests that run against the real API and database (workflow `.github/workflows/e2e.yml`).
Screenshots of every admin page (desktop, phone, dark) and key storefront pages are published to the
`e2e-shots` branch on each pull request. Accessibility (axe, WCAG 2.1 AA) is enforced for the admin and
reported for the storefront.

To run locally, with the API on :8000 (seeded) and the storefront on :3000:

```bash
cd e2e && npm install && npx playwright install chromium
ADMIN_EMAIL=… ADMIN_PASSWORD=… E2E_BASE_URL=http://localhost:3000 E2E_API_URL=http://localhost:8000/api/v1 npx playwright test
npm run test:unit   # pure helpers: number/date formatting, date ranges
```
