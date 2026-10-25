/**
 * SelfFint data layer — everything through `ctx.rest`, i.e. the plugin's own
 * `/api/plugins/self-fint/*` door served by `packages/selffint/src/selffint/api.py`.
 *
 * The rules this module keeps:
 *  - the mirror lives on the gateway and reports are computed there, so the page
 *    never does accounting arithmetic (two implementations, two answers);
 *  - a demo site is a first-class state, not an error: the service seeds one on a
 *    first run and every payload carries `mode` so the UI can badge it;
 *  - money is rendered here but never rounded differently from the server — the
 *    server sends floats already quantised to paise.
 */

import {
  atom,
  type PluginOs,
  type PluginRestOptions,
  type PluginStorage,
  type PluginTranslate,
  queryClient
} from '@beyond/plugin-sdk'

type Rest = <T>(path: string, opts?: PluginRestOptions) => Promise<T>

export type Mode = 'demo' | 'live'

export interface SiteInfo {
  id: string
  url: string
  label: string
  mode: Mode
  has_credentials: boolean
  created_at: string
}

export interface SyncState {
  doctype: string
  watermark: string
  rows: number
  synced_at: string
  ok: boolean
  error: string
}

export interface ServiceStatus {
  ok: true
  site: SiteInfo
  sites: SiteInfo[]
  counts: Record<string, number>
  syncs: SyncState[]
  last_sync: string
  warnings: string[]
  supported_doctypes: string[]
}

export interface InvoiceRow {
  name: string
  customer: string
  posting_date: string
  due_date: string
  grand_total: number
  outstanding_amount: number
  status: string
  docstatus: number
  currency: string
}

export interface PartyRow {
  name: string
  display: string
  group: string
  territory: string
}

export interface AgingBucket {
  key: string
  label: string
  amount: number
  count: number
  share: number
}

export interface AgingReport {
  as_of: string
  total: number
  overdue: number
  open_invoices: number
  buckets: AgingBucket[]
  by_customer: { amount: number; customer: string; invoices: number; oldest_days: number }[]
}

export interface GstRow {
  rate: number
  taxable: number
  cgst: number
  sgst: number
  igst: number
  cess: number
  total: number
  invoices: number
}

export interface GstReport {
  from: string
  to: string
  invoices: number
  rows: GstRow[]
  taxable: number
  cgst: number
  sgst: number
  igst: number
  cess: number
  total_tax: number
  exempt: number
  unallocated: number
}

export interface PayrollReport {
  month: string
  slips: number
  gross: number
  deductions: number
  net: number
  employer_contribution: number
  cost_to_company: number
  employees: { deductions: number; employee: string; gross: number; net: number; slips: number }[]
}

export interface ReconRow {
  status: string
  gstin: string
  invoice_number: string
  book_tax: number
  portal_tax: number
  itc_at_risk: number
  note: string
}

export interface ReconReport {
  summary: {
    period: string
    matched: number
    tax_mismatch: number
    missing_in_2b: number
    missing_in_books: number
    probable: number
    duplicates: number
    book_tax: number
    portal_tax: number
    net_difference: number
    itc_at_risk: number
  }
  rows: ReconRow[]
}

export type Tab = 'invoices' | 'overview' | 'parties' | 'reports'

const STORE_KEYS = { tab: 'tab' } as const
const TABS: readonly Tab[] = ['invoices', 'overview', 'parties', 'reports']

let rest: null | Rest = null
let t: PluginTranslate = key => key

/** Which pane is open. Persisted so a restart lands where the user left. */
export const $tab = atom<Tab>('overview')
/** Invoice/party filter. Deliberately not persisted — a stale search reads as an
 *  empty ledger on the next launch. */
export const $search = atom<string>('')
/** Which report the Reports tab shows. */
export const $report = atom<'aging' | 'credit' | 'gst' | 'payroll'>('aging')

const KEY_ROOT = ['self-fint'] as const

export const statusKey = () => [...KEY_ROOT, 'status'] as const
export const invoicesKey = (search: string) => [...KEY_ROOT, 'invoices', search] as const
export const partiesKey = (kind: string, search: string) => [...KEY_ROOT, 'parties', kind, search] as const
export const agingKey = (asOf: string) => [...KEY_ROOT, 'aging', asOf] as const
export const gstKey = (from: string, to: string) => [...KEY_ROOT, 'gst', from, to] as const
export const payrollKey = (month: string) => [...KEY_ROOT, 'payroll', month] as const
export const reconKey = () => [...KEY_ROOT, 'recon'] as const

export function invalidateAll(): void {
  void queryClient.invalidateQueries({ queryKey: KEY_ROOT })
}

export function bindApi(
  apiRest: Rest,
  storage: PluginStorage,
  _socket: (path: string, onMessage: (data: unknown) => void) => () => void,
  opts: { os: PluginOs; t: PluginTranslate }
): () => void {
  rest = apiRest
  t = opts.t

  const saved = storage.get<Tab>(STORE_KEYS.tab, 'overview')

  $tab.set(TABS.includes(saved) ? saved : 'overview')

  const unsub = $tab.listen(value => storage.set(STORE_KEYS.tab, value))

  return () => {
    unsub()
    rest = null
    t = key => key
  }
}

function needRest(): Rest {
  if (!rest) {
    throw new Error(t('notReady'))
  }

  return rest
}

// ------------------------------------------------------------------ queries
export async function fetchStatus(): Promise<ServiceStatus> {
  return needRest()<ServiceStatus>('/status')
}

export async function fetchInvoices(search = ''): Promise<InvoiceRow[]> {
  const suffix = search ? `?search=${encodeURIComponent(search)}` : ''
  const result = await needRest()<{ invoices: InvoiceRow[] }>(`/invoices${suffix}`)

  return result.invoices
}

export async function fetchParties(kind: 'customer' | 'supplier', search = ''): Promise<PartyRow[]> {
  const query = `?kind=${kind}${search ? `&search=${encodeURIComponent(search)}` : ''}`
  const result = await needRest()<{ parties: PartyRow[] }>(`/parties${query}`)

  return result.parties
}

/** Reports arrive with an `ok` envelope flag; the pane only wants the report, so
 *  the flag is stripped here rather than leaking into every component's type. */
function report<T extends object>(result: T & { ok?: true }): T {
  const { ok: _ok, ...body } = result

  return body as T
}

export async function fetchAging(asOf = ''): Promise<AgingReport> {
  const result = await needRest()<AgingReport & { ok: true }>(
    `/reports/ar-aging${asOf ? `?as_of=${asOf}` : ''}`
  )

  return report(result)
}

export async function fetchGst(from = '', to = ''): Promise<GstReport> {
  const query = new URLSearchParams()

  if (from) {
    query.set('from', from)
  }

  if (to) {
    query.set('to', to)
  }

  const suffix = query.toString() ? `?${query.toString()}` : ''

  return report(await needRest()<GstReport & { ok: true }>(`/reports/gst${suffix}`))
}

export async function fetchPayroll(month = ''): Promise<PayrollReport> {
  const result = await needRest()<PayrollReport & { ok: true }>(
    `/reports/payroll${month ? `?month=${month}` : ''}`
  )

  return report(result)
}

export async function reconcileDemo(period = ''): Promise<ReconReport> {
  return needRest()<ReconReport>('/reconcile/2b', {
    body: { period, use_demo: true },
    method: 'POST'
  })
}

// ----------------------------------------------------------------- commands
export interface ConnectInput {
  url: string
  api_key: string
  api_secret: string
  label?: string
}

export async function connectSite(input: ConnectInput): Promise<{ site: SiteInfo; user: string }> {
  const result = await needRest()<{ ok: true; site: SiteInfo; user: string }>('/connect', {
    body: input,
    method: 'POST'
  })

  invalidateAll()

  return { site: result.site, user: result.user }
}

export interface SyncReport {
  ok: boolean
  mode: Mode
  rows?: number
  doctypes?: { doctype: string; rows: number; hydrated: number; ok: boolean; error: string }[]
}

export async function runSync(): Promise<SyncReport> {
  const result = await needRest()<SyncReport>('/sync', { body: {}, method: 'POST' })

  invalidateAll()

  return result
}

export interface DraftInvoiceInput {
  customer: string
  posting_date?: string
  due_date?: string
  items: { description: string; qty: number; rate: number }[]
}

export async function createDraftInvoice(input: DraftInvoiceInput): Promise<{ name: string }> {
  const result = await needRest()<{ ok: true; document: { name: string } }>('/invoices', {
    body: input,
    method: 'POST'
  })

  invalidateAll()

  return result.document
}

// ------------------------------------------------------------------ formatting
const INR = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 0, minimumFractionDigits: 0 })
const INR_PAISE = new Intl.NumberFormat('en-IN', { maximumFractionDigits: 2, minimumFractionDigits: 2 })

/** `₹1,18,000` — Indian digit grouping, which `en-US` gets wrong. */
export function money(value: number, opts: { paise?: boolean } = {}): string {
  const formatter = opts.paise ? INR_PAISE : INR

  return `₹${formatter.format(Number.isFinite(value) ? value : 0)}`
}

/** Compact money for KPI tiles: `₹2.4L`, `₹1.2Cr` — the units a finance desk uses. */
export function compactMoney(value: number): string {
  const amount = Number.isFinite(value) ? Math.abs(value) : 0
  const sign = value < 0 ? '-' : ''

  if (amount >= 1e7) {
    return `${sign}₹${(amount / 1e7).toFixed(2)}Cr`
  }

  if (amount >= 1e5) {
    return `${sign}₹${(amount / 1e5).toFixed(2)}L`
  }

  return `${sign}${money(amount)}`
}

/** Days a document is past due, or a negative number of days until it is. */
export function daysPastDue(dueDate: string, today = new Date()): number {
  const due = Date.parse(`${dueDate}T00:00:00`)

  if (Number.isNaN(due)) {
    return 0
  }

  const start = Date.parse(`${today.toISOString().slice(0, 10)}T00:00:00`)

  return Math.round((start - due) / 86_400_000)
}

export function documentStatusLabel(row: InvoiceRow): string {
  if (row.docstatus === 0) {
    return 'Draft'
  }

  if (row.docstatus === 2) {
    return 'Cancelled'
  }

  return row.status || 'Open'
}
