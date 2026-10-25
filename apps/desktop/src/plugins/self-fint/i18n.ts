/**
 * SelfFint's own message bundle, registered under the plugin id. Core English is
 * never touched; the page reads through `useSelfFintI18n()` so a missing key is a
 * type error rather than a raw string in the UI.
 */

import { type PluginLocaleBundles, usePluginI18n } from '@beyond/plugin-sdk'
import { useMemo } from 'react'

export type SelfFintMessages = {
  nav: string
  open: string
  title: string
  subtitle: string
  notReady: string
  loading: string
  retry: string
  // tabs
  overview: string
  invoices: string
  parties: string
  reports: string
  // status
  connected: string
  demoMode: string
  demoBanner: string
  site: string
  siteUrl: string
  lastSync: string
  never: string
  syncNow: string
  syncing: string
  synced: (rows: number) => string
  connect: string
  connectTitle: string
  connectHint: string
  apiKey: string
  apiSecret: string
  url: string
  label: string
  connecting: string
  connectedAs: (user: string) => string
  disconnect: string
  // kpis
  receivables: string
  overdue: string
  outputTax: string
  payrollCost: string
  itcAtRisk: string
  openInvoices: (count: number) => string
  documents: string
  // invoices
  searchInvoices: string
  noInvoices: string
  noInvoicesHint: string
  invoice: string
  customer: string
  posted: string
  due: string
  total: string
  outstanding: string
  status: string
  draft: string
  newInvoice: string
  createDraft: string
  creating: string
  draftHint: string
  itemDescription: string
  qty: string
  rate: string
  addItem: string
  removeItem: string
  amount: string
  // parties
  customers: string
  supplier: string
  suppliers: string
  noParties: string
  employee: string
  group: string
  territory: string
  // reports
  aging: string
  gst: string
  payroll: string
  credit: string
  asOf: string
  bucket: string
  share: string
  from: string
  to: string
  taxable: string
  exempt: string
  unallocated: string
  unallocatedHint: string
  month: string
  gross: string
  deductions: string
  net: string
  employerContribution: string
  costToCompany: string
  slips: (count: number) => string
  noReport: string
  reconTitle: string
  reconHint: string
  runRecon: string
  running: string
  matched: string
  mismatch: string
  missingIn2b: string
  missingInBooks: string
  probable: string
  duplicates: string
  invoiceNo: string
  bookTax: string
  portalTax: string
  difference: string
  // misc
  demoBadge: string
  empty: string
  error: string
}

const EN: SelfFintMessages = {
  addItem: 'Add line',
  aging: 'Ageing',
  amount: 'Amount',
  apiKey: 'API key',
  apiSecret: 'API secret',
  asOf: 'As of',
  bookTax: 'Book tax',
  bucket: 'Bucket',
  connect: 'Connect a site',
  connectHint:
    'Create an API key and secret on the site under User ▸ API Access, then paste them here. The secret is stored on this machine only.',
  connectTitle: 'Connect an ERP site',
  connected: 'Connected',
  connectedAs: (user: string) => `Connected as ${user}`,
  connecting: 'Connecting…',
  costToCompany: 'Cost to company',
  createDraft: 'Save draft',
  creating: 'Saving…',
  credit: 'Input credit',
  customer: 'Customer',
  customers: 'Customers',
  deductions: 'Deductions',
  demoBadge: 'Demo data',
  demoBanner: 'This is the demo company — fixture data, not your books. Connect a site to see real numbers.',
  demoMode: 'Demo company',
  difference: 'Difference',
  disconnect: 'Disconnect',
  documents: 'Documents in the mirror',
  draft: 'Draft',
  draftHint: 'Saved as a draft on the site. Nothing is posted to the ledger from here.',
  due: 'Due',
  duplicates: 'Duplicates',
  employerContribution: 'Employer contribution',
  empty: 'Nothing here yet',
  employee: 'Employee',
  error: 'Something went wrong',
  exempt: 'Exempt',
  from: 'From',
  gross: 'Gross',
  group: 'Group',
  gst: 'GST',
  invoice: 'Invoice',
  invoiceNo: 'Invoice no.',
  invoices: 'Invoices',
  itemDescription: 'Description',
  itcAtRisk: 'ITC at risk',
  label: 'Label',
  lastSync: 'Last sync',
  loading: 'Loading…',
  matched: 'Matched',
  mismatch: 'Tax mismatch',
  missingIn2b: 'Missing in 2B',
  missingInBooks: 'Missing in books',
  month: 'Month',
  nav: 'SelfFint',
  net: 'Net pay',
  never: 'never',
  newInvoice: 'New invoice',
  noInvoices: 'No invoices match',
  noInvoicesHint: 'Sync the site, or clear the search.',
  noParties: 'No parties in the mirror yet',
  noReport: 'Run a sync to fill this report.',
  notReady: 'The SelfFint service is not connected.',
  open: 'Open SelfFint',
  openInvoices: (count: number) => `${count} open`,
  outputTax: 'Output tax',
  outstanding: 'Outstanding',
  overdue: 'Overdue',
  parties: 'Parties',
  payroll: 'Payroll',
  payrollCost: 'Payroll cost',
  portalTax: 'Portal tax',
  posted: 'Posted',
  probable: 'Probable',
  qty: 'Qty',
  rate: 'Rate',
  receivables: 'Receivables',
  reconHint: 'Matches the purchase register against a GSTR-2B file and shows the credit at risk.',
  reconTitle: 'Input credit against GSTR-2B',
  removeItem: 'Remove',
  reports: 'Reports',
  retry: 'Retry',
  runRecon: 'Reconcile the demo 2B',
  running: 'Working…',
  searchInvoices: 'Search invoices',
  share: 'Share',
  site: 'Site',
  siteUrl: 'Site URL',
  slips: (count: number) => `${count} slips`,
  status: 'Status',
  subtitle: 'Receivables, GST, input credit and payroll — read from your ERP.',
  supplier: 'Supplier',
  suppliers: 'Suppliers',
  syncNow: 'Sync now',
  syncing: 'Syncing…',
  synced: (rows: number) => `${rows} documents synced`,
  taxable: 'Taxable',
  territory: 'Territory',
  title: 'SelfFint',
  to: 'To',
  total: 'Total',
  unallocated: 'Unallocated',
  unallocatedHint: 'Invoices without tax rows — open them on the site or re-sync to allocate them.',
  url: 'https://erp.example.com',
  overview: 'Overview'
}

export const SELF_FINT_LOCALES: PluginLocaleBundles = { en: EN }

export function useSelfFintI18n(): SelfFintMessages {
  const t = usePluginI18n('self-fint')
  const messages = useMemo(() => t as unknown as SelfFintMessages, [t])

  return messages
}
