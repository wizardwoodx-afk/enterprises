# Third-Party Licenses and Attribution

Beyond is an independent product built on two upstream source trees: a desktop
application published by **Nous Research**, and an agent engine published by
**CrewAI, Inc.** This file is the single place where upstream names, copyright
holders and package identities are recorded — everything user-facing, every
identifier, asset and env var in the rest of this repository uses the Beyond and
Beholders names.

---

## 1. Upstream application source (Beyond)

The desktop application in `apps/desktop` and `apps/shared`, together with the
build tooling in `scripts/` and the test assets in `tests/`, are derived from
the **Hermes Agent** project by **Nous Research**.

| | |
|---|---|
| Project | Hermes Agent / Hermes Desktop |
| Copyright | Copyright (c) 2025 **Nous Research** |
| Repository | https://github.com/**NousResearch/hermes-agent** |
| Mirrored commit | `4ea8d23cc9f527332ccb1d55359b27741b6ea51b` (2026-10-24) |
| License | MIT |
| Website | https://**hermes-agent.nousresearch.com** |

The MIT license text is reproduced in full in [`LICENSE`](./LICENSE), which is
retained verbatim because the MIT license requires the copyright notice and
permission notice to accompany any redistributed copy of the source. It is a
third-party notice file, not a Beyond brand asset.

### Modifications

This redistribution is **modified** from the original. Relative to upstream, the
Beyond fork has:

- renamed the product, every identifier, environment variable, asset, host and
  route from *Hermes* / *Nous* to *Beyond*, across ~2,700 source files;
- replaced the application icon set with an original geometric Beyond mark,
  generated deterministically by `tools/generate-beyond-icons.py`;
- removed the original brand-kit artwork (`nous-girl` marks, sample art and the
  SVG icon pipeline that consumed them);
- retargeted the root workspace manifest to the subset of the monorepo that is
  vendored here.

No upstream source file carries an endorsement of this redistribution.

---

## 2. Upstream agent engine (Beholders)

`packages/beholders` — the crew runtime behind Beyond's **Beholders** page — is
vendored from the **CrewAI** framework. The engine's domain vocabulary is kept
deliberately: a *crew*, an *agent*, a *task*, a *flow* and a *kickoff* mean what
they meant upstream, because they are the framework's public API and because
Beyond's UI is a view onto it. Only the product name changed.

| | |
|---|---|
| Package | `beholders` (an independent distribution, vendored in-tree) |
| Upstream project | CrewAI |
| Copyright | Copyright (c) 2025 **CrewAI, Inc.** |
| Repository | https://github.com/**crewAIInc/crewAI** |
| Mirrored commit | `38db11e3324fa0e23beb5eecd0d87e8e31ca2bb0` (2026-10-23, v1.15.30) |
| License | MIT — reproduced verbatim in [`packages/beholders/LICENSE`](./packages/beholders/LICENSE) |
| Website | https://**crewai.com** |

Only two of the upstream monorepo's published distributions are vendored:
`crewai` (as `beholders`) and `crewai-core` (as `beholders_core`). They are
merged into **one** installable distribution, so the upstream `crewai-core` /
`crewai-cli` pins disappear. The CLI distribution is not vendored: Beyond ships
its own `beholders` entry point (`beholders.service.cli`) on top of the service
layer.

### Modifications

Relative to upstream, this vendor tree has:

- renamed every module, identifier, environment variable and host:
  `crewai` → `beholders`, `crewai_core` → `beholders_core`,
  `crewai.com` → `beyond.app`, plus the `CREWAI_*` → `BEHOLDERS_*` env vars;
- **disabled telemetry in code**, not by flag: `Telemetry._is_telemetry_disabled`
  returns `True` unless a caller explicitly opts in, so no `TracerProvider` or
  OTLP exporter is ever constructed and no span leaves the machine. The
  collector constant is additionally non-routable (`telemetry.invalid`);
- dropped the upstream CLI package and its deprecation shim
  (`beholders/cli/__init__.py`), which merely proxied a distribution that is not
  vendored;
- made the package import lazy (`beholders/__init__.py`), so the service layer
  and its tests import without the engine's third-party dependency tree;
- added `beholders/service/` — crew storage, a run registry with cancellation and
  event fan-out, a REST surface, a `crew.*` JSON-RPC surface and a stdlib HTTP
  adapter. This layer is original to Beyond;
- excluded the upstream `docs/` (415 MB of product documentation) and the
  recorded HTTP cassettes under `tests/`.

No upstream source file carries an endorsement of this redistribution.

---

## 3. Third-party package names that cannot be renamed

Some dependencies are **published packages whose names are fixed by the npm
registry**. Renaming them would break installation, so they keep their original
identifiers inside `package.json`, `package-lock.json` and `node_modules` — and
nowhere else. Beyond does not claim any affiliation with their publishers.

| Package | Version | Publisher | License | Why the name stays |
|---|---|---|---|---|
| `@nous-research/ui` | 0.18.2 | Nous Research | MIT | Published npm package; a dependency of the desktop renderer |
| `hermes-parser` | 0.25.1 | Meta Platforms (Babel/Metro ecosystem) | MIT | Published npm package; transitive build dependency |
| `hermes-estree` | 0.25.1 | Meta Platforms (Babel/Metro ecosystem) | MIT | Published npm package; transitive build dependency |
| `hermes` | 0.0.0 | — | — | Registry resolution entry for the above |

`hermes-parser` / `hermes-estree` are unrelated to the Hermes Agent project: they
are Meta's JavaScript parser used across the React Native / Metro toolchain.

### Third-party model identifiers

`packages/beholders/src/beholders/llms/litellm_catalog/model_prices_and_context_window.json`
is a vendored snapshot of published model prices and context windows. Its keys
are **provider model ids** (`<provider>/<publisher>/<model>`), some of which carry
the name of the model's publisher or of a model family. They are registry
identities in exactly the sense the npm names above are: renaming one breaks
model resolution. The file is excluded from the branding guard for that reason
and appears nowhere else in the tree.

---

## 4. Other bundled third-party software

The desktop app bundles or links the following, each under its own license. The
authoritative license text for each ships with the package in `node_modules/`
and is embedded into packaged builds by electron-builder's `LICENSES.chromium.html`
and `resources/` notices.

| Component | License |
|---|---|
| Electron, Chromium, Node.js | MIT / BSD-3-Clause / Apache-2.0 |
| React, React DOM | MIT |
| Vite, Rolldown, esbuild | MIT |
| Tailwind CSS | MIT |
| assistant-ui (`@assistant-ui/*`) | MIT |
| CodeMirror (`@codemirror/*`, `@lezer/*`) | MIT |
| Shiki, Streamdown, KaTeX, Mermaid | MIT |
| xterm.js (`@xterm/*`) | MIT |
| TanStack Query / Virtual | MIT |
| Radix UI, Lucide, Tabler icons | MIT |
| nanostores, motion, cmdk, d3-force | MIT |
| node-pty, simple-git, ignore, yaml, semver | MIT |
| Zod | MIT |
| Playwright (dev) | Apache-2.0 |
| Vitest (dev) | MIT |
| Python, if bundled in installer variants | PSF-2.0 |
| Beholders engine dependencies (pydantic, httpx, chromadb, lancedb, openai, opentelemetry, …) | MIT / Apache-2.0 / BSD |

Fonts bundled under `apps/desktop/src/fonts` remain under their original
licenses as shipped with their packages.

---

## 5. Trademarks

"Hermes", "Nous", "Nous Research" and the Nous Research logo are trademarks or
registered trademarks of Nous Research. "CrewAI" and the CrewAI logo are
trademarks or registered trademarks of CrewAI, Inc. "Beyond", "Beholders" and
their marks are used by this project.

Nothing in this repository grants any right to use the Nous Research or CrewAI
marks, and this project is not affiliated with, sponsored by, or endorsed by
either company.

---

## 6. Reporting an attribution gap

If you believe a component is missing from this file, please open an issue with
the package name and version. Attribution errors are treated as bugs.
