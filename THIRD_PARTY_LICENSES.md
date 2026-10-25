# Third-Party Licenses and Attribution

Beyond is an independent product built on a source tree originally published by
**Nous Research**. This file is the single place where upstream names,
copyright holders and package identities are recorded — everything
user-facing, every identifier, asset and env var in the rest of this repository
uses the Beyond name.

---

## 1. Upstream application source

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

## 2. Third-party package names that cannot be renamed

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

---

## 3. Other bundled third-party software

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

Fonts bundled under `apps/desktop/src/fonts` remain under their original
licenses as shipped with their packages.

---

## 4. Trademarks

"Hermes", "Nous", "Nous Research" and the Nous Research logo are trademarks or
registered trademarks of Nous Research. "Beyond" and the Beyond mark are used by
this project. Nothing in this repository grants any right to use the Nous
Research marks, and this project is not affiliated with, sponsored by, or
endorsed by Nous Research.

---

## 5. Reporting an attribution gap

If you believe a component is missing from this file, please open an issue with
the package name and version. Attribution errors are treated as bugs.
