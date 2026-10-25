/**
 * SelfFint — the finance pane.
 *
 * One rule shapes the whole page: every number comes from the service
 * (`packages/selffint`), never from arithmetic done here. The page fetches
 * already-computed reports and renders them, so the browser and the CLI can
 * never disagree about what the ageing schedule says.
 *
 * SDK-only — no `@/…` imports, so this file would compile unchanged as a
 * runtime-fetched published plugin.
 */

import {
  Badge,
  Button,
  cn,
  EmptyState,
  ErrorState,
  GlyphSpinner,
  Input,
  useMutation,
  useQuery,
  useQueryClient,
  useValue
} from '@beyond/plugin-sdk'
import { useMemo, useState } from 'react'

import {
  $report,
  $search,
  $tab,
  agingKey,
  type AgingReport,
  compactMoney,
  connectSite,
  createDraftInvoice,
  daysPastDue,
  documentStatusLabel,
  fetchAging,
  fetchGst,
  fetchInvoices,
  fetchParties,
  fetchPayroll,
  fetchStatus,
  gstKey,
  type GstReport,
  type InvoiceRow,
  invoicesKey,
  type Mode,
  money,
  partiesKey,
  payrollKey,
  type PayrollReport,
  reconcileDemo,
  type ReconReport,
  runSync,
  type ServiceStatus,
  statusKey,
  type Tab
} from './api'
import { useSelfFintI18n } from './i18n'

// ------------------------------------------------------------------------ bits

function Spinner({ label }: { label: string }) {
  return (
    <div className="flex items-center gap-2 p-3 text-xs text-muted-foreground">
      <GlyphSpinner className="text-xs" />
      {label}
    </div>
  )
}

function ModeBadge({ mode }: { mode: Mode }) {
  const k = useSelfFintI18n()

  return (
    <Badge variant={mode === 'live' ? 'success' : 'warn'}>
      {mode === 'live' ? k.connected : k.demoBadge}
    </Badge>
  )
}

function Kpi({ hint, label, value }: { hint?: string; label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-[3px] border border-(--ui-stroke-tertiary) px-2.5 py-2">
      <div className="truncate text-[0.625rem] uppercase tracking-wide text-muted-foreground">{label}</div>
      <div className="mt-0.5 truncate text-sm font-semibold tabular-nums text-foreground">{value}</div>
      {hint && <div className="truncate text-[0.6875rem] text-muted-foreground">{hint}</div>}
    </div>
  )
}

function Section({ children, className, title }: { children: React.ReactNode; className?: string; title: string }) {
  return (
    <section className="min-w-0 rounded-[3px] border border-(--ui-stroke-tertiary)">
      <h3 className="border-b border-(--ui-stroke-tertiary) px-2.5 py-1.5 text-[0.6875rem] font-medium text-foreground">
        {title}
      </h3>
      <div className={cn('p-2.5', className)}>{children}</div>
    </section>
  )
}

/** The one table treatment this pane uses: hairline rules, tabular numerals,
 *  right-aligned money. Kept local — the SDK ships no Table primitive. */
function DataTable<T>({
  columns,
  empty,
  rows,
  rowKey
}: {
  columns: { align?: 'right'; cell: (row: T) => React.ReactNode; header: string; key: string }[]
  empty?: string
  rows: T[]
  rowKey: (row: T) => string
}) {
  if (rows.length === 0 && empty) {
    return <EmptyState title={empty} />
  }

  return (
    <div className="min-w-0 overflow-x-auto">
      <table className="w-full border-collapse text-xs">
        <thead>
          <tr className="text-[0.625rem] uppercase tracking-wide text-muted-foreground">
            {columns.map(column => (
              <th
                className={cn(
                  'border-b border-(--ui-stroke-tertiary) px-1.5 py-1 font-normal',
                  column.align === 'right' ? 'text-right' : 'text-left'
                )}
                key={column.key}
              >
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map(row => (
            <tr className="align-middle hover:bg-(--chrome-action-hover)" key={rowKey(row)}>
              {columns.map(column => (
                <td
                  className={cn(
                    'border-b border-(--ui-stroke-tertiary)/60 px-1.5 py-1 text-foreground',
                    column.align === 'right' ? 'text-right tabular-nums' : 'text-left'
                  )}
                  key={column.key}
                >
                  {column.cell(row)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function Tabs() {
  const k = useSelfFintI18n()
  const tab = useValue($tab)

  const items: { id: Tab; label: string }[] = [
    { id: 'overview', label: k.overview },
    { id: 'invoices', label: k.invoices },
    { id: 'parties', label: k.parties },
    { id: 'reports', label: k.reports }
  ]

  return (
    <div className="flex shrink-0 gap-0.5 border-b border-(--ui-stroke-tertiary) px-2" role="tablist">
      {items.map(item => (
        <button
          aria-selected={tab === item.id}
          className={cn(
            'cursor-pointer border-b-2 px-2.5 py-1.5 text-xs',
            tab === item.id
              ? 'border-primary font-medium text-foreground'
              : 'border-transparent text-muted-foreground hover:text-foreground'
          )}
          key={item.id}
          onClick={() => $tab.set(item.id)}
          role="tab"
          type="button"
        >
          {item.label}
        </button>
      ))}
    </div>
  )
}

// ------------------------------------------------------------------ status bar

function StatusBar({ status }: { status: ServiceStatus }) {
  const k = useSelfFintI18n()
  const queryClient = useQueryClient()
  const [connecting, setConnecting] = useState(false)

  const sync = useMutation({
    mutationFn: async () => runSync(),
    onSuccess: () => queryClient.invalidateQueries()
  })

  return (
    <div className="shrink-0 border-b border-(--ui-stroke-tertiary)">
      <div className="flex flex-wrap items-center gap-x-2 gap-y-1 px-2.5 py-1.5 text-[0.6875rem]">
        <ModeBadge mode={status.site.mode} />
        <span className="max-w-[16rem] truncate text-muted-foreground" title={status.site.url}>
          {status.site.mode === 'demo' ? k.demoMode : status.site.label}
        </span>
        <span className="text-muted-foreground">
          {k.lastSync}: {status.last_sync || k.never}
        </span>
        <div className="ml-auto flex items-center gap-1">
          {sync.data && (
            <span className="text-muted-foreground">
              {sync.data.ok ? k.synced(sync.data.rows ?? 0) : k.error}
            </span>
          )}
          <Button disabled={sync.isPending} onClick={() => sync.mutate()} size="xs" variant="ghost">
            {sync.isPending ? k.syncing : k.syncNow}
          </Button>
          <Button onClick={() => setConnecting(value => !value)} size="xs" variant="ghost">
            {k.connect}
          </Button>
        </div>
      </div>
      {connecting && <ConnectForm onDone={() => setConnecting(false)} />}
    </div>
  )
}

function ConnectForm({ onDone }: { onDone: () => void }) {
  const k = useSelfFintI18n()
  const queryClient = useQueryClient()
  const [url, setUrl] = useState('')
  const [apiKey, setApiKey] = useState('')
  const [apiSecret, setApiSecret] = useState('')

  const mutation = useMutation({
    mutationFn: async () => connectSite({ api_key: apiKey, api_secret: apiSecret, url }),
    onSuccess: () => {
      void queryClient.invalidateQueries()
      onDone()
    }
  })

  return (
    <form
      className="flex flex-wrap items-end gap-2 border-b border-(--ui-stroke-tertiary) bg-(--ui-bg-secondary) px-2.5 py-2"
      onSubmit={event => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <label className="flex min-w-48 flex-1 flex-col gap-0.5">
        <span className="text-[0.625rem] text-muted-foreground">{k.siteUrl}</span>
        <Input onChange={event => setUrl(event.target.value)} placeholder="https://erp.example.com" value={url} />
      </label>
      <label className="flex flex-col gap-0.5">
        <span className="text-[0.625rem] text-muted-foreground">{k.apiKey}</span>
        <Input onChange={event => setApiKey(event.target.value)} value={apiKey} />
      </label>
      <label className="flex flex-col gap-0.5">
        <span className="text-[0.625rem] text-muted-foreground">{k.apiSecret}</span>
        <Input onChange={event => setApiSecret(event.target.value)} type="password" value={apiSecret} />
      </label>
      <Button disabled={mutation.isPending || !url || !apiKey || !apiSecret} size="sm" type="submit">
        {mutation.isPending ? k.connecting : k.connect}
      </Button>
      <p className="w-full text-[0.6875rem] text-muted-foreground">{k.connectHint}</p>
      {mutation.isError && (
        <p className="w-full text-[0.6875rem] text-destructive">{(mutation.error as Error).message}</p>
      )}
    </form>
  )
}

// -------------------------------------------------------------------- overview

function AgingMini({ report }: { report: AgingReport }) {
  return (
    <table className="w-full text-xs">
      <tbody>
        {report.buckets.map(bucket => (
          <tr key={bucket.key}>
            <td className="py-0.5 text-muted-foreground">{bucket.label}</td>
            <td className="py-0.5 text-right tabular-nums text-foreground">{money(bucket.amount)}</td>
            <td className="w-12 py-0.5 text-right tabular-nums text-muted-foreground">
              {bucket.count > 0 ? `${Math.round(bucket.share * 100)}%` : '—'}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function Overview({ status }: { status: ServiceStatus }) {
  const k = useSelfFintI18n()
  const aging = useQuery({ queryFn: async () => fetchAging(), queryKey: agingKey('') })
  const gst = useQuery({ queryFn: async () => fetchGst(), queryKey: gstKey('', '') })
  const payroll = useQuery({ queryFn: async () => fetchPayroll(), queryKey: payrollKey('') })

  return (
    <div className="flex flex-col gap-2 overflow-y-auto p-2.5">
      {status.site.mode === 'demo' && (
        <p className="rounded-[3px] border border-amber-500/30 bg-amber-500/10 px-2 py-1.5 text-[0.6875rem] text-muted-foreground">
          {k.demoBanner}
        </p>
      )}
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <Kpi
          hint={aging.data ? k.openInvoices(aging.data.open_invoices) : undefined}
          label={k.receivables}
          value={aging.data ? compactMoney(aging.data.total) : '—'}
        />
        <Kpi label={k.overdue} value={aging.data ? compactMoney(aging.data.overdue) : '—'} />
        <Kpi
          hint={gst.data ? `${k.exempt}: ${compactMoney(gst.data.exempt)}` : undefined}
          label={k.outputTax}
          value={gst.data ? compactMoney(gst.data.total_tax) : '—'}
        />
        <Kpi
          hint={payroll.data ? k.slips(payroll.data.slips) : undefined}
          label={k.payrollCost}
          value={payroll.data ? compactMoney(payroll.data.cost_to_company) : '—'}
        />
      </div>
      <div className="grid gap-2 lg:grid-cols-2">
        <Section title={k.aging}>
          {aging.data ? <AgingMini report={aging.data} /> : <Spinner label={k.loading} />}
        </Section>
        <Section title={k.documents}>
          <div className="grid grid-cols-2 gap-x-3 gap-y-1">
            {Object.entries(status.counts).map(([doctype, count]) => (
              <div className="flex items-baseline justify-between gap-2 text-xs" key={doctype}>
                <span className="truncate text-muted-foreground">{doctype}</span>
                <span className="tabular-nums text-foreground">{count}</span>
              </div>
            ))}
          </div>
        </Section>
      </div>
      {status.warnings.length > 0 && (
        <ul className="list-disc pl-5 text-[0.6875rem] text-amber-600 dark:text-amber-300">
          {status.warnings.map(warning => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

// -------------------------------------------------------------------- invoices

function InvoiceTable({ invoices }: { invoices: InvoiceRow[] }) {
  const k = useSelfFintI18n()

  const columns = useMemo(
    () => [
      {
        cell: (row: InvoiceRow) => <span className="font-medium">{row.name}</span>,
        header: k.invoice,
        key: 'name'
      },
      { cell: (row: InvoiceRow) => row.customer, header: k.customer, key: 'customer' },
      { cell: (row: InvoiceRow) => row.posting_date, header: k.posted, key: 'posted' },
      {
        cell: (row: InvoiceRow) => {
          const late = row.outstanding_amount > 0 && daysPastDue(row.due_date) > 0

          return <span className={late ? 'text-destructive' : undefined}>{row.due_date}</span>
        },
        header: k.due,
        key: 'due'
      },
      { align: 'right' as const, cell: (row: InvoiceRow) => money(row.grand_total), header: k.total, key: 'total' },
      {
        align: 'right' as const,
        cell: (row: InvoiceRow) => (
          <span className={row.outstanding_amount > 0 ? 'font-medium' : 'text-muted-foreground'}>
            {money(row.outstanding_amount)}
          </span>
        ),
        header: k.outstanding,
        key: 'outstanding'
      },
      {
        cell: (row: InvoiceRow) => (
          <Badge variant={row.docstatus === 0 ? 'warn' : row.docstatus === 2 ? 'destructive' : 'muted'}>
            {documentStatusLabel(row)}
          </Badge>
        ),
        header: k.status,
        key: 'status'
      }
    ],
    [k]
  )

  return <DataTable columns={columns} empty={k.noInvoices} rowKey={row => row.name} rows={invoices} />
}

function DraftForm() {
  const k = useSelfFintI18n()
  const queryClient = useQueryClient()
  const [open, setOpen] = useState(false)
  const [customer, setCustomer] = useState('')
  const [description, setDescription] = useState('')
  const [qty, setQty] = useState('1')
  const [rate, setRate] = useState('')

  const mutation = useMutation({
    mutationFn: async () =>
      createDraftInvoice({
        customer,
        items: [{ description: description || 'Services', qty: Number(qty) || 1, rate: Number(rate) || 0 }]
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries()
      setOpen(false)
      setDescription('')
      setRate('')
    }
  })

  if (!open) {
    return (
      <Button onClick={() => setOpen(true)} size="sm" variant="secondary">
        {k.newInvoice}
      </Button>
    )
  }

  return (
    <form
      className="flex flex-wrap items-end gap-1.5 rounded-[3px] border border-(--ui-stroke-tertiary) p-2"
      onSubmit={event => {
        event.preventDefault()
        mutation.mutate()
      }}
    >
      <Input onChange={event => setCustomer(event.target.value)} placeholder={k.customer} value={customer} />
      <Input
        onChange={event => setDescription(event.target.value)}
        placeholder={k.itemDescription}
        value={description}
      />
      <Input className="w-14" onChange={event => setQty(event.target.value)} value={qty} />
      <Input className="w-20" onChange={event => setRate(event.target.value)} placeholder={k.rate} value={rate} />
      <Button disabled={mutation.isPending || !customer || !rate} size="sm" type="submit">
        {mutation.isPending ? k.creating : k.createDraft}
      </Button>
      <span className="w-full text-[0.6875rem] text-muted-foreground">{k.draftHint}</span>
      {mutation.isError && (
        <span className="w-full text-[0.6875rem] text-destructive">{(mutation.error as Error).message}</span>
      )}
    </form>
  )
}

function Invoices() {
  const k = useSelfFintI18n()
  const search = useValue($search)
  const invoices = useQuery({ queryFn: async () => fetchInvoices(search), queryKey: invoicesKey(search) })

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 flex-wrap items-center gap-1.5 p-2.5">
        <Input
          className="max-w-64"
          onChange={event => $search.set(event.target.value)}
          placeholder={k.searchInvoices}
          value={search}
        />
        <DraftForm />
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-2.5 pb-2.5">
        {invoices.isLoading ? (
          <Spinner label={k.loading} />
        ) : invoices.data ? (
          <InvoiceTable invoices={invoices.data} />
        ) : (
          <EmptyState title={k.error} />
        )}
      </div>
    </div>
  )
}

// --------------------------------------------------------------------- parties

function Parties() {
  const k = useSelfFintI18n()
  const search = useValue($search)
  const [kind, setKind] = useState<'customer' | 'supplier'>('customer')
  const parties = useQuery({ queryFn: async () => fetchParties(kind, search), queryKey: partiesKey(kind, search) })

  const columns = useMemo(
    () => [
      {
        cell: (row: { display: string }) => <span className="font-medium">{row.display}</span>,
        header: kind === 'customer' ? k.customer : k.supplier,
        key: 'display'
      },
      { cell: (row: { group: string }) => row.group || '—', header: k.group, key: 'group' },
      { cell: (row: { territory: string }) => row.territory || '—', header: k.territory, key: 'territory' }
    ],
    [k, kind]
  )

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 items-center gap-1.5 p-2.5">
        <Button onClick={() => setKind('customer')} size="xs" variant={kind === 'customer' ? 'secondary' : 'ghost'}>
          {k.customers}
        </Button>
        <Button onClick={() => setKind('supplier')} size="xs" variant={kind === 'supplier' ? 'secondary' : 'ghost'}>
          {k.suppliers}
        </Button>
        <Input
          className="max-w-64"
          onChange={event => $search.set(event.target.value)}
          placeholder={kind === 'customer' ? k.customers : k.suppliers}
          value={search}
        />
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-2.5 pb-2.5">
        {parties.isLoading ? (
          <Spinner label={k.loading} />
        ) : parties.data ? (
          <DataTable
            columns={columns}
            empty={k.noParties}
            rowKey={row => row.name}
            rows={parties.data}
          />
        ) : (
          <EmptyState title={k.error} />
        )}
      </div>
    </div>
  )
}

// --------------------------------------------------------------------- reports

function GstPanel() {
  const k = useSelfFintI18n()
  const gst = useQuery({ queryFn: async () => fetchGst(), queryKey: gstKey('', '') })

  const columns = useMemo(
    () => [
      { cell: (row: GstReport['rows'][number]) => `${row.rate}%`, header: k.rate, key: 'rate' },
      {
        align: 'right' as const,
        cell: (row: GstReport['rows'][number]) => String(row.invoices),
        header: k.invoices,
        key: 'invoices'
      },
      { align: 'right' as const, cell: (row: GstReport['rows'][number]) => money(row.taxable), header: k.taxable, key: 'taxable' },
      { align: 'right' as const, cell: (row: GstReport['rows'][number]) => money(row.cgst), header: 'CGST', key: 'cgst' },
      { align: 'right' as const, cell: (row: GstReport['rows'][number]) => money(row.sgst), header: 'SGST', key: 'sgst' },
      { align: 'right' as const, cell: (row: GstReport['rows'][number]) => money(row.igst), header: 'IGST', key: 'igst' },
      { align: 'right' as const, cell: (row: GstReport['rows'][number]) => money(row.total), header: k.total, key: 'total' }
    ],
    [k]
  )

  if (!gst.data) {
    return <Spinner label={k.loading} />
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <Kpi label={k.taxable} value={money(gst.data.taxable)} />
        <Kpi label={k.outputTax} value={money(gst.data.total_tax)} />
        <Kpi label={k.exempt} value={money(gst.data.exempt)} />
        <Kpi label={k.unallocated} value={money(gst.data.unallocated)} />
      </div>
      <DataTable columns={columns} rowKey={row => String(row.rate)} rows={gst.data.rows} />
      {gst.data.unallocated > 0 && <p className="text-[0.6875rem] text-amber-600 dark:text-amber-300">{k.unallocatedHint}</p>}
    </div>
  )
}

function AgingPanel() {
  const k = useSelfFintI18n()
  const aging = useQuery({ queryFn: async () => fetchAging(), queryKey: agingKey('') })

  if (!aging.data) {
    return <Spinner label={k.loading} />
  }

  return (
    <div className="flex flex-col gap-2">
      <DataTable
        columns={[
          { cell: (row: AgingReport['buckets'][number]) => row.label, header: k.bucket, key: 'label' },
          { align: 'right', cell: (row: AgingReport['buckets'][number]) => String(row.count), header: k.invoices, key: 'count' },
          { align: 'right', cell: (row: AgingReport['buckets'][number]) => money(row.amount), header: k.amount, key: 'amount' },
          { align: 'right', cell: (row: AgingReport['buckets'][number]) => `${Math.round(row.share * 100)}%`, header: k.share, key: 'share' }
        ]}
        rowKey={row => row.key}
        rows={aging.data.buckets}
      />
      <Section title={k.customers}>
        <table className="w-full text-xs">
          <thead className="text-[0.625rem] uppercase tracking-wide text-muted-foreground">
            <tr>
              <th className="text-left font-normal">{k.customer}</th>
              <th className="text-right font-normal">{k.invoices}</th>
              <th className="text-right font-normal">{k.outstanding}</th>
            </tr>
          </thead>
          <tbody>
            {aging.data.by_customer.map(row => (
              <tr key={row.customer}>
                <td className="py-0.5 text-muted-foreground">{row.customer}</td>
                <td className="py-0.5 text-right tabular-nums text-muted-foreground">{row.invoices}</td>
                <td className="py-0.5 text-right font-medium tabular-nums">{money(row.amount)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Section>
    </div>
  )
}

function CreditPanel() {
  const k = useSelfFintI18n()
  const [report, setReport] = useState<ReconReport | null>(null)
  const mutation = useMutation({ mutationFn: async () => reconcileDemo(), onSuccess: value => setReport(value) })

  const columns = useMemo(
    () => [
      {
        cell: (row: ReconReport['rows'][number]) => (
          <Badge variant={row.status === 'matched' ? 'success' : row.itc_at_risk > 0 ? 'destructive' : 'warn'}>
            {row.status}
          </Badge>
        ),
        header: k.status,
        key: 'status'
      },
      { cell: (row: ReconReport['rows'][number]) => row.gstin || '—', header: 'GSTIN', key: 'gstin' },
      { cell: (row: ReconReport['rows'][number]) => row.invoice_number || '—', header: k.invoiceNo, key: 'invoice' },
      { align: 'right' as const, cell: (row: ReconReport['rows'][number]) => money(row.book_tax), header: k.bookTax, key: 'book' },
      { align: 'right' as const, cell: (row: ReconReport['rows'][number]) => money(row.portal_tax), header: k.portalTax, key: 'portal' },
      {
        align: 'right' as const,
        cell: (row: ReconReport['rows'][number]) => (
          <span className={row.itc_at_risk > 0 ? 'font-medium text-destructive' : undefined}>
            {money(row.itc_at_risk)}
          </span>
        ),
        header: k.itcAtRisk,
        key: 'risk'
      }
    ],
    [k]
  )

  return (
    <div className="flex flex-col gap-2">
      <Section title={k.reconTitle}>
        <div className="flex flex-wrap items-center gap-2">
          <Button disabled={mutation.isPending} onClick={() => mutation.mutate()} size="sm">
            {mutation.isPending ? k.running : k.runRecon}
          </Button>
          <span className="text-[0.6875rem] text-muted-foreground">{k.reconHint}</span>
        </div>
        {report && (
          <div className="mt-2 grid grid-cols-2 gap-2 lg:grid-cols-4">
            <Kpi label={k.matched} value={String(report.summary.matched)} />
            <Kpi label={k.mismatch} value={String(report.summary.tax_mismatch)} />
            <Kpi label={k.missingIn2b} value={String(report.summary.missing_in_2b)} />
            <Kpi label={k.itcAtRisk} value={money(report.summary.itc_at_risk)} />
          </div>
        )}
      </Section>
      {report && <DataTable columns={columns} rowKey={row => `${row.gstin}-${row.invoice_number}`} rows={report.rows} />}
    </div>
  )
}

function PayrollPanel() {
  const k = useSelfFintI18n()
  const payroll = useQuery({ queryFn: async () => fetchPayroll(), queryKey: payrollKey('') })

  const columns = useMemo(
    () => [
      {
        cell: (row: PayrollReport['employees'][number]) => <span className="font-medium">{row.employee}</span>,
        header: k.employee,
        key: 'employee'
      },
      { align: 'right' as const, cell: (row: PayrollReport['employees'][number]) => String(row.slips), header: k.invoices, key: 'slips' },
      { align: 'right' as const, cell: (row: PayrollReport['employees'][number]) => money(row.gross), header: k.gross, key: 'gross' },
      { align: 'right' as const, cell: (row: PayrollReport['employees'][number]) => money(row.deductions), header: k.deductions, key: 'deductions' },
      { align: 'right' as const, cell: (row: PayrollReport['employees'][number]) => money(row.net), header: k.net, key: 'net' }
    ],
    [k]
  )

  if (!payroll.data) {
    return <Spinner label={k.loading} />
  }

  return (
    <div className="flex flex-col gap-2">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-4">
        <Kpi label={k.gross} value={money(payroll.data.gross)} />
        <Kpi label={k.employerContribution} value={money(payroll.data.employer_contribution)} />
        <Kpi label={k.costToCompany} value={money(payroll.data.cost_to_company)} />
        <Kpi label={k.month} value={payroll.data.month || k.never} />
      </div>
      <DataTable columns={columns} rowKey={row => row.employee} rows={payroll.data.employees} />
    </div>
  )
}

function Reports() {
  const k = useSelfFintI18n()
  const report = useValue($report)

  const choices: { id: typeof report; label: string }[] = [
    { id: 'aging', label: k.aging },
    { id: 'gst', label: k.gst },
    { id: 'credit', label: k.credit },
    { id: 'payroll', label: k.payroll }
  ]

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="flex shrink-0 flex-wrap items-center gap-1 p-2.5">
        {choices.map(choice => (
          <Button
            key={choice.id}
            onClick={() => $report.set(choice.id)}
            size="xs"
            variant={report === choice.id ? 'secondary' : 'ghost'}
          >
            {choice.label}
          </Button>
        ))}
      </div>
      <div className="min-h-0 flex-1 overflow-auto px-2.5 pb-2.5">
        {report === 'aging' && <AgingPanel />}
        {report === 'gst' && <GstPanel />}
        {report === 'credit' && <CreditPanel />}
        {report === 'payroll' && <PayrollPanel />}
      </div>
    </div>
  )
}

// ------------------------------------------------------------------------ page

export function SelfFintPage() {
  const k = useSelfFintI18n()
  const status = useQuery({ queryFn: async () => fetchStatus(), queryKey: statusKey() })
  const tab = useValue($tab)

  if (status.isLoading) {
    return <Spinner label={k.loading} />
  }

  if (status.isError || !status.data) {
    return (
      <div className="p-6">
        <ErrorState description={k.notReady} title={k.error}>
          <Button onClick={() => void status.refetch()} size="sm" variant="secondary">
            {k.retry}
          </Button>
        </ErrorState>
      </div>
    )
  }

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex shrink-0 items-baseline gap-2 px-2.5 pt-2">
        <h2 className="text-sm font-semibold text-foreground">{k.title}</h2>
        <p className="min-w-0 truncate text-[0.6875rem] text-muted-foreground">{k.subtitle}</p>
      </div>
      <StatusBar status={status.data} />
      <Tabs />
      <div className="flex min-h-0 flex-1 flex-col">
        {tab === 'overview' && <Overview status={status.data} />}
        {tab === 'invoices' && <Invoices />}
        {tab === 'parties' && <Parties />}
        {tab === 'reports' && <Reports />}
      </div>
    </div>
  )
}
