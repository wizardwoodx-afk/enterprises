# Branding

Beyond is a debranded distribution. The product name, mark, identifiers, assets
and environment namespace are Beyond everywhere in this repository, with two
deliberate exceptions documented below.

## The name

| Context | Value |
|---|---|
| Product / display name | `Beyond` |
| Workspace package (`apps/desktop`) | `beyond` |
| Root workspace | `beyond-desktop` |
| Shared library | `@beyond/shared` |
| npm scope | `@beyond/*` |
| CLI command | `beyond` |
| Env-var namespace | `BEYOND_*` |
| User data directory | `BEYOND_HOME` (`~/.beyond`, `%LOCALAPPDATA%\beyond`) |
| macOS / Windows app id | `app.beyond.beyond` (variants: `app.beyond.beyond-light`, …) |
| Windows MSIX package | `beyond-app.Beyond…` |
| Preview bridge | `window.beyondDesktop` |
| Hosts | `beyond.app`, `portal.beyond.app`, `api.beyond.app`, `*.agents.beyond.app` |

## The mark

An original geometric mark: a squircle tile in an indigo→violet gradient with a
double forward chevron. Everything is generated from one source,
[`tools/generate-beyond-icons.py`](../tools/generate-beyond-icons.py), which
emits 86 files:

- `assets/icon.png`, `icon-dark.png`, `icon-mac.png` (1024²)
- `assets/icon.icns`, `icon-dark.icns`, `packaging/dmg-volume.icns`
- `assets/icon.ico`, `icon-dark.ico`
- every Windows `assets/appx/*.png` tile at its existing pixel size
- the macOS 26 Icon Composer package `assets/icon.icon/Assets/*`
- `public/apple-touch-icon.png`, `public/beyond.png`, `public/beyond-sprite.png`
- the in-app badge `public/beyond-mark.png` / `beyond-mark-dark.png`
- the onboarding frames `public/beyond-frames/*.png`

```bash
python3 tools/generate-beyond-icons.py           # write
python3 tools/generate-beyond-icons.py --check   # verify presence
```

Requires Pillow. The output is deterministic, so CI can regenerate and assert a
clean `git diff`.

This replaced the inherited brand-kit pipeline (a mascot SVG plus the Python
drawer that composed it). Those SVGs were never part of this tree, so the old
pipeline was non-functional here; it has been removed along with its test.

## What the debrand touched

~2,700 files, ~23,000 replacements, applied in dependency order (hosts and
compound identifiers before generic word swaps) so no compound survived as
`beyond-beyond`:

| Class | Beyond value |
|---|---|
| Hosts | `beyond.app`, `portal.beyond.app`, `api.beyond.app` |
| Cloud agents | `<name>.agents.beyond.app` |
| Env vars | `BEYOND_HOME`, `BEYOND_DESKTOP_VARIANT`, `BEYOND_DESKTOP_*` |
| App id | `app.beyond.<variant>` |
| npm scope | `@beyond/*` |
| Wire ids | `beyond-3` |
| Assets | `beyond-mark.png`, `beyond-mark-dark.png`, `beyond.png`, `beyond-sprite.png` |
| Files | `src/beyond.ts`, `src/types/beyond.ts`, `electron/windows-beyond-path.ts` |
| Directories | `src/plugins/beyond-bots/` |
| Copy | `Beyond`, `Beyond Portal`, `Beyond Cloud`, `Beyond Light` |

The pre-rename strings are deliberately **not** reproduced here; they exist only
in [`THIRD_PARTY_LICENSES.md`](../THIRD_PARTY_LICENSES.md).

String identifiers, i18n catalogs in all 12 locales, docs, tests, fixtures and
build tooling were all rewritten together, so source and assertions stay in
sync (typecheck and the test suite confirm this).

## Beholders — the second debrand

The crew runtime in `packages/beholders` was vendored from a separate upstream
and debranded to **Beholders** under the same rule: the upstream name appears
only in the license files (`THIRD_PARTY_LICENSES.md` §2 and
`packages/beholders/LICENSE`). The mechanical rules, in order:

| Class | Beholders value |
|---|---|
| Module (longest first) | `beholders_core`, `beholders_cli`, `beholders` |
| Env vars | `BEHOLDERS_HOME`, `BEHOLDERS_*` |
| Hosts | `beyond.app`, `docs.beyond.app`, `app.beyond.app`, `login.beyond.app` |
| CLI | `beholders` |
| Copy | `Beholders` |

Two things were **not** renamed, on purpose:

- **The domain vocabulary.** `Crew`, `Agent`, `Task`, `Flow`, `Process` and
  `kickoff` are the engine's public API. See
  [`BEHOLDERS.md`](./BEHOLDERS.md) §1.
- **The upstream engine's own third-party license text**, kept verbatim in
  `packages/beholders/LICENSE`.

Telemetry was switched off in code rather than renamed — a renamed collector
would still be a collector. See [`BEHOLDERS.md`](./BEHOLDERS.md) §6.

## The two deliberate exceptions

1. **`LICENSE`** keeps the upstream copyright notice verbatim. The MIT license
   requires the notice and permission text to travel with redistributed source;
   stripping it would make the redistribution non-compliant. Treat it as a
   third-party notice file, not a brand asset.

2. **`package-lock.json` / `package.json`** keep the fixed names of *published*
   npm packages from third-party registries. These are registry identities, not
   branding: renaming them breaks installation. They appear nowhere else in the
   tree — the list is in
   [`THIRD_PARTY_LICENSES.md`](../THIRD_PARTY_LICENSES.md) §2.

Both exceptions, plus the full upstream attribution, are recorded in
[`THIRD_PARTY_LICENSES.md`](../THIRD_PARTY_LICENSES.md).

A CI job (`.github/workflows/verify.yml` → `debrand`) enforces this for **both**
upstreams: any occurrence of either upstream's mark outside those files fails the
build.

## Rebranding checklist for new code

- Use `Beyond` in copy, `beyond` in identifiers, `BEYOND_` in env vars.
- Use `Beholders` in copy, `beholders` in identifiers, `BEHOLDERS_` in env vars,
  for anything belonging to the crew runtime.
- Never hard-code a host; read it from `apps/shared` or `electron/connection-config.ts`.
- Add new icons to `tools/generate-beyond-icons.py`, not by hand.
- If you must reference a fixed third-party package name, it belongs in
  `THIRD_PARTY_LICENSES.md`.
