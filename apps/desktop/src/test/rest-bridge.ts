import { vi } from 'vitest'

import type { BeyondApiRequest } from '@/global'

/** Install a fake `window.beyondDesktop.api`, the preload bridge every REST helper sends through. */
export function installRestBridge(answer: (request: BeyondApiRequest) => object) {
  const api = vi.fn(async (request: BeyondApiRequest) => answer(request))

  Object.defineProperty(window, 'beyondDesktop', { configurable: true, value: { api } })

  return api
}
