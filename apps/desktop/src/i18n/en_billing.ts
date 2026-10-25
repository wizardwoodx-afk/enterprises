import type { BillingTranslations } from './types_billing'

// Out-of-credits overlay copy (Beyond vs. third-party providers), spread into en.ts.
export const enBilling: BillingTranslations = {
  billingBlock: {
    titleBeyond: 'Out of Beyond credits',
    titleProvider: provider => `Out of credits — ${provider}`,
    fallbackMessage: 'Your account is out of credits. Add credits to keep going.',
    openBilling: 'Open billing',
    addCredits: 'Add credits',
    dismiss: 'Dismiss'
  }
}
