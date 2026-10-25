/**
 * The Beholders crew contract, re-exported into the plugin SDK.
 *
 * The shapes themselves live in `@beyond/shared/crew-contract`, next to the
 * other cross-process contracts, because the Python service
 * (`packages/beholders/src/beholders/service/models.py`) mirrors them field for
 * field. Plugins may not import `@beyond/shared` directly (lint-fenced), so this
 * module is the one door they use — the same treatment `./areas` gives the
 * contribution-slot types.
 */

export * from '@beyond/shared/crew-contract'
