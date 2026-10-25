#!/usr/bin/env bash
# Re-sync this mirror against NousResearch/hermes-agent.
#
#   ./tools/sync-upstream.sh                 # sync to the commit pinned in upstream.json
#   ./tools/sync-upstream.sh --check         # report drift, change nothing
#   ./tools/sync-upstream.sh --latest        # sync to the tip of upstream `main`
#   ./tools/sync-upstream.sh --ref <sha>     # sync to an explicit commit/tag
#   ./tools/sync-upstream.sh --with-agent-core
#                                              # also vendor the Python agent core
#                                              # (~233 MB / 21k files — see PROVENANCE.md)
#
# The mirror layout is path-identical to upstream, so every relative import
# (`../shared`, `../../tests-js`, `../../scripts/...`) keeps resolving and the
# only files this script never overwrites are the mirror-local ones listed in
# `referenceOnlyPaths` (package.json, lockfile, README, .gitignore).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
MANIFEST="$ROOT/upstream.json"
CACHE="$ROOT/.upstream/hermes-agent"
REFERENCE="$ROOT/.upstream/reference"

MODE="sync"
REF=""
WITH_CORE=0

usage() { sed -n '2,18p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

while [ $# -gt 0 ]; do
  case "$1" in
    --check) MODE="check" ;;
    --latest) MODE="latest" ;;
    --ref) REF="${2:?--ref needs a commit or tag}"; shift ;;
    --with-agent-core) WITH_CORE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "unknown option: $1" >&2; usage >&2; exit 2 ;;
  esac
  shift
done

command -v git >/dev/null || { echo "git is required" >&2; exit 1; }
[ -f "$MANIFEST" ] || { echo "missing $MANIFEST" >&2; exit 1; }

# --- read the manifest -------------------------------------------------------
meta() { node -e '
  const m = require(process.argv[1]);
  const key = process.argv[2];
  const out = m.source[key] ?? "";
  process.stdout.write(String(out));
' "$MANIFEST" "$1"; }

REPO="$(meta repository)"
PINNED="$(meta commit)"
BRANCH="$(meta branch)"

case "$MODE" in
  latest) TARGET_BRANCH="$BRANCH"; TARGET_SHA="" ;;
  *)      TARGET_BRANCH="";        TARGET_SHA="${REF:-$PINNED}" ;;
esac

# --- fetch a blobless sparse checkout of upstream ----------------------------
mkdir -p "$(dirname "$CACHE")"
if [ ! -d "$CACHE/.git" ]; then
  echo "→ cloning $REPO (blobless, sparse)"
  git clone --filter=blob:none --no-checkout --depth 1 "$REPO" "$CACHE" >/dev/null 2>&1
fi
git -C "$CACHE" remote set-url origin "$REPO"

echo "→ fetching ${TARGET_SHA:-$TARGET_BRANCH}"
if [ -n "$TARGET_SHA" ]; then
  git -C "$CACHE" fetch --depth 1 origin "$TARGET_SHA" >/dev/null 2>&1 \
    || { echo "could not fetch $TARGET_SHA from $REPO" >&2; exit 1; }
  git -C "$CACHE" checkout -q --detach FETCH_HEAD 2>/dev/null \
    || git -C "$CACHE" checkout -q --detach "$TARGET_SHA"
else
  git -C "$CACHE" fetch --depth 1 origin "$BRANCH" >/dev/null 2>&1
  git -C "$CACHE" checkout -q --detach FETCH_HEAD
fi

# Sparse-checkout exactly what this mirror vendors (plus root reference files).
mapfile -t INCLUDE < <(node -e '
  const m = require(process.argv[1]);
  for (const p of m.includedPaths) console.log(p);
  if (process.argv[2] === "1") {
    for (const p of ["agent","hermes_cli","gateway","tools","skills","optional-skills",
                     "plugins","web","ui-tui","locales"]) console.log(p);
  }
' "$MANIFEST" "$WITH_CORE")
mapfile -t REFONLY < <(node -e '
  const m = require(process.argv[1]);
  for (const p of m.referenceOnlyPaths) console.log(p);
' "$MANIFEST")

# Add both the file form and the directory form of every pattern: a bare name
# like "LICENSE" has no extension to sniff, and sparse-checkout silently yields
# nothing for a trailing-slash pattern that does not name a directory.
PATTERNS=()
for p in "${INCLUDE[@]}" "${REFONLY[@]}"; do PATTERNS+=("/$p" "/$p/"); done
git -C "$CACHE" sparse-checkout set --no-cone "${PATTERNS[@]}" >/dev/null 2>&1
git -C "$CACHE" checkout -q 2>/dev/null || true

ACTUAL_SHA="$(git -C "$CACHE" rev-parse HEAD)"
ACTUAL_DATE="$(git -C "$CACHE" log -1 --format=%cI)"

copy_path() { # $1 = relative path, $2 = destination root
  local rel="$1" dest="$2"
  [ -e "$CACHE/$rel" ] || { echo "  ! not in upstream: $rel" >&2; return 1; }
  mkdir -p "$(dirname "$dest/$rel")"
  if [ -d "$CACHE/$rel" ]; then
    mkdir -p "$dest/$rel"
    if command -v rsync >/dev/null; then
      rsync -a --delete "$CACHE/$rel/" "$dest/$rel/"
    else
      ( cd "$CACHE/$rel" && tar cf - . ) | ( cd "$dest/$rel" && tar xf - )
    fi
  else
    cp -a "$CACHE/$rel" "$dest/$rel"
  fi
}

if [ "$MODE" = "check" ]; then
  echo "→ drift check against $ACTUAL_SHA ($ACTUAL_DATE)"
  # Build outputs are gitignored generated state, never source: exclude them or
  # every check after a local `npm run build` reports false drift.
  DIFF_OPTS=(-rq -x node_modules -x build -x dist -x release -x '.staging-*' -x '.dist-build*')
  drift=0
  for p in "${INCLUDE[@]}"; do
    [ -e "$CACHE/$p" ] || continue
    if diff "${DIFF_OPTS[@]}" "$CACHE/$p" "$ROOT/$p" >/dev/null 2>&1; then
      printf '  = %s\n' "$p"
    else
      printf '  ~ %s\n' "$p"
      diff "${DIFF_OPTS[@]}" "$CACHE/$p" "$ROOT/$p" 2>/dev/null | head -5 | sed 's/^/      /'
      drift=1
    fi
  done
  [ "$drift" -eq 0 ] && echo "✓ in sync with $ACTUAL_SHA" || echo "✗ drift found (run without --check to apply)"
  exit "$drift"
fi

echo "→ syncing $ACTUAL_SHA ($ACTUAL_DATE) into $ROOT"
for p in "${INCLUDE[@]}"; do copy_path "$p" "$ROOT" && printf '  ✓ %s\n' "$p"; done

mkdir -p "$REFERENCE"
for p in "${REFONLY[@]}"; do
  [ -e "$CACHE/$p" ] && cp -a "$CACHE/$p" "$REFERENCE/$(basename "$p")" || true
done

FILES="$(git -C "$ROOT" status --porcelain --untracked-files=all 2>/dev/null | wc -l | tr -d ' ')"
cat <<EOF

✓ sync complete
  upstream : $REPO
  commit   : $ACTUAL_SHA
  date     : $ACTUAL_DATE
  changed  : $FILES path(s) now differ in the working tree

Next: update "source.commit"/"commitDate" in upstream.json, then
      npm install && npm run typecheck --workspace apps/desktop
EOF
