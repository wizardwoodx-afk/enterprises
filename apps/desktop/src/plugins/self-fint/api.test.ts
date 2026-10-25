/**
 * The SelfFint data layer: the URL each command builds, the shapes it unwraps,
 * and the money formatting the pane depends on. The service has its own pytest
 * suite; nothing here re-checks arithmetic that belongs to the server — only the
 * Indian digit grouping and the day maths, which live on this side of the wire.
 */

import { type PluginRestOptions, type PluginStorage } from '@beyond/plugin-sdk'
import { afterEach, describe, expect, it, vi } from 'vitest'

import {
  $tab,
  bindApi,
  compactMoney,
  createDraftInvoice,
  daysPastDue,
  documentStatusLabel,
  fetchAging,
  fetchGst,
  fetchInvoices,
  fetchParties,
  fetchPayroll,
  fetchStatus,
  type InvoiceRow,
  money,
  reconcileDemo,
  runSync
} from './api'

type Call = { path: string; opts?: PluginRestOptions }

const storage = (seed: Record<string, unknown> = {}): PluginStorage => ({
  get: <T,>(key: string, fallback: T) => (key in seed ? (seed[key] as T) : fallback),
  remove: vi.fn(),
  set: vi.fn()
})

function harness(reply: (call: Call) => unknown, seed: Record<string, unknown> = {}) {
  const calls: Call[] = []

  const rest = async <T,>(path: string, opts?: PluginRestOptions): Promise<T> => {
    const call = { opts, path }

    calls.push(call)

    return reply(call) as T
  }

  const dispose = bindApi(rest, storage(seed), () => () => undefined, { os: {} as never, t: key => key })

  return { calls, dispose, rest }
}

let teardown: (() => void) | null = null

afterEach(() => {
  teardown?.()
  teardown = null
})

describe('commands', () => {
  it('refuses to work before the plugin is registered', async () => {
    await expect(fetchStatus()).rejects.toThrow()
  })

  it('reads status through its own namespace', async () => {
    const h = harness(() => ({ ok: true, site: {}, sites: [], counts: {}, syncs: [], last_sync: '', warnings: [], supported_doctypes: [] }))

    teardown = h.dispose
    await fetchStatus()
    expect(h.calls[0].path).toBe('/status')
  })

  it('encodes the invoice search instead of interpolating it raw', async () => {
    const h = harness(() => ({ invoices: [] }))

    teardown = h.dispose
    await fetchInvoices('Acme & Sons')
    expect(h.calls[0].path).toBe('/invoices?search=Acme%20%26%20Sons')
  })

  it('omits the search parameter when the box is empty', async () => {
    const h = harness(() => ({ invoices: [] }))

    teardown = h.dispose
    await fetchInvoices('')
    expect(h.calls[0].path).toBe('/invoices')
  })

  it('asks for the party kind and keeps the search', async () => {
    const h = harness(() => ({ parties: [] }))

    teardown = h.dispose
    await fetchParties('supplier', 'Kumar')
    expect(h.calls[0].path).toBe('/parties?kind=supplier&search=Kumar')
  })

  it('unwraps the report envelopes rather than handing the whole payload on', async () => {
    const h = harness(() => ({ buckets: [], by_customer: [], ok: true, total: 0 }))

    teardown = h.dispose
    const aging = await fetchAging('2026-10-20')
    expect(h.calls[0].path).toBe('/reports/ar-aging?as_of=2026-10-20')
    expect(aging).not.toHaveProperty('ok')
    expect(aging.buckets).toEqual([])
  })

  it('builds a date range for GST only from what the caller set', async () => {
    const h = harness(() => ({ ok: true, rows: [] }))

    teardown = h.dispose
    await fetchGst('2026-04-01', '')
    expect(h.calls[0].path).toBe('/reports/gst?from=2026-04-01')
    await fetchPayroll('2026-09')
    expect(h.calls[1].path).toBe('/reports/payroll?month=2026-09')
  })

  it('sends a draft invoice as a POST body, never as query parameters', async () => {
    const h = harness(() => ({ document: { name: 'SINV-0001' }, ok: true }))

    teardown = h.dispose

    const created = await createDraftInvoice({
      customer: 'Acme',
      items: [{ description: 'Work', qty: 2, rate: 500 }]
    })

    expect(created.name).toBe('SINV-0001')
    expect(h.calls[0].opts?.method).toBe('POST')
    expect(h.calls[0].opts?.body).toMatchObject({ customer: 'Acme' })
  })

  it('syncs with an empty body and reports what happened', async () => {
    const h = harness(() => ({ doctypes: [], mode: 'demo', ok: true, rows: 12 }))

    teardown = h.dispose
    expect((await runSync()).rows).toBe(12)
    expect(h.calls[0].opts?.method).toBe('POST')
  })

  it('reconciles against the demo 2B by default', async () => {
    const h = harness(() => ({ rows: [], summary: {} }))

    teardown = h.dispose
    await reconcileDemo()
    expect(h.calls[0].opts?.body).toMatchObject({ use_demo: true })
  })

  it('remembers the tab across a restart and ignores a stale value', () => {
    const fresh = harness(() => ({}), { tab: 'reports' })

    expect($tab.get()).toBe('reports')
    fresh.dispose()

    const stale = harness(() => ({}), { tab: 'ledger-from-an-older-build' })

    expect($tab.get()).toBe('overview')
    stale.dispose()
  })
})

describe('formatting', () => {
  it('groups digits the Indian way, not the western way', () => {
    expect(money(1234567)).toBe('₹12,34,567')
    expect(money(0)).toBe('₹0')
    expect(money(-4500)).toBe('₹-4,500')
  })

  it('keeps paise only when asked', () => {
    expect(money(1180.5)).toBe('₹1,181')
    expect(money(1180.5, { paise: true })).toBe('₹1,180.50')
  })

  it('compacts to lakh and crore', () => {
    expect(compactMoney(240_000)).toBe('₹2.40L')
    expect(compactMoney(12_500_000)).toBe('₹1.25Cr')
    expect(compactMoney(9_500)).toBe('₹9,500')
    expect(compactMoney(-240_000)).toBe('-₹2.40L')
  })

  it('survives a NaN rather than printing ₹NaN', () => {
    expect(money(Number.NaN)).toBe('₹0')
    expect(compactMoney(Number.NaN)).toBe('₹0')
  })

  it('counts whole days past due and goes negative before the due date', () => {
    expect(daysPastDue('2026-10-01', new Date('2026-10-20T09:00:00Z'))).toBe(19)
    expect(daysPastDue('2026-10-20', new Date('2026-10-20T09:00:00Z'))).toBe(0)
    expect(daysPastDue('2026-11-01', new Date('2026-10-20T09:00:00Z'))).toBe(-12)
    expect(daysPastDue('not-a-date')).toBe(0)
  })

  it('labels a document by docstatus before trusting the server status', () => {
    const row = (over: Partial<InvoiceRow>) =>
      ({ docstatus: 1, outstanding_amount: 0, status: 'Paid', ...over }) as InvoiceRow

    expect(documentStatusLabel(row({ docstatus: 0 }))).toBe('Draft')
    expect(documentStatusLabel(row({ docstatus: 2 }))).toBe('Cancelled')
    expect(documentStatusLabel(row({ status: 'Overdue' }))).toBe('Overdue')
    expect(documentStatusLabel(row({ status: '' }))).toBe('Open')
  })
})
