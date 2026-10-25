import type {
  BeyondGitBaseBranch,
  BeyondGitBranch,
  BeyondGitWorktree,
  BeyondRepoPullRequests,
  BeyondRepoStatus,
  BeyondReviewList,
  BeyondReviewShipInfo
} from '@/global'
import { beyondApi } from '@/beyond'

import { desktopFsProfile, isDesktopFsRemoteMode } from './desktop-fs'

// Remote-aware git facade. Locally the desktop runs git through Electron
// (window.beyondDesktop.git); on a remote gateway that's the wrong filesystem,
// so we mirror the same surface over the dashboard REST API (/api/git/*) — the
// coding rail, worktree lanes, review pane, and branch ops then act on the
// BACKEND repo where sessions actually run. Mirrors desktop-fs.ts.

type GitBridge = NonNullable<NonNullable<Window['beyondDesktop']>['git']>

function desktopApi<T>(path: string, body?: Record<string, unknown>): Promise<T> {
  const desktop = window.beyondDesktop

  if (!desktop) {
    throw new Error('Beyond Desktop bridge is unavailable')
  }

  return beyondApi<T>(
    body ? { body, method: 'POST', path, profile: desktopFsProfile() } : { path, profile: desktopFsProfile() }
  )
}

function gitGet<T>(route: string, params: Record<string, boolean | null | string | undefined>): Promise<T> {
  const query = new URLSearchParams()

  for (const [key, value] of Object.entries(params)) {
    if (value !== null && value !== undefined) {
      query.set(key, String(value))
    }
  }

  return desktopApi<T>(`/api/git/${route}?${query.toString()}`)
}

function gitPost<T>(route: string, body: Record<string, unknown>): Promise<T> {
  return desktopApi<T>(`/api/git/${route}`, body)
}

const remoteGit: GitBridge = {
  worktreeList: async repoPath =>
    (await gitGet<{ worktrees: BeyondGitWorktree[] }>('worktrees', { path: repoPath })).worktrees,

  worktreeAdd: (repoPath, options) => gitPost('worktree/add', { path: repoPath, ...options }),

  worktreeRemove: (repoPath, worktreePath, options) =>
    gitPost('worktree/remove', { force: options?.force ?? false, path: repoPath, worktreePath }),

  branchSwitch: (repoPath, branch) => gitPost('branch/switch', { branch, path: repoPath }),

  branchList: async repoPath =>
    (await gitGet<{ branches: BeyondGitBranch[] }>('branches', { path: repoPath })).branches,

  baseBranchList: async repoPath =>
    (await gitGet<{ branches: BeyondGitBaseBranch[] }>('base-branches', { path: repoPath })).branches,

  repoStatus: repoPath => gitGet<BeyondRepoStatus | null>('status', { path: repoPath }),

  fileDiff: async (repoPath, filePath) =>
    (await gitGet<{ diff: string }>('file-diff', { file: filePath, path: repoPath })).diff,

  review: {
    list: (repoPath, scope, baseRef) =>
      gitGet<BeyondReviewList>('review/list', { base: baseRef, path: repoPath, scope }),

    diff: async (repoPath, filePath, scope, baseRef, staged) =>
      (await gitGet<{ diff: string }>('review/diff', { base: baseRef, file: filePath, path: repoPath, scope, staged }))
        .diff,

    stage: (repoPath, filePath) => gitPost('review/stage', { file: filePath ?? null, path: repoPath }),

    unstage: (repoPath, filePath) => gitPost('review/unstage', { file: filePath ?? null, path: repoPath }),

    revert: (repoPath, filePath) => gitPost('review/revert', { file: filePath ?? null, path: repoPath }),

    revParse: async (repoPath, ref) =>
      (await gitGet<{ sha: null | string }>('review/rev-parse', { path: repoPath, ref })).sha,

    commit: (repoPath, message, push) => gitPost('review/commit', { message, path: repoPath, push }),

    commitContext: repoPath => gitGet('review/commit-context', { path: repoPath }),

    push: repoPath => gitPost('review/push', { path: repoPath }),

    shipInfo: repoPath => gitGet<BeyondReviewShipInfo>('review/ship-info', { path: repoPath }),

    prList: (repoPath, branches, numbers) =>
      gitPost<BeyondRepoPullRequests>('review/pr-list', { branches, numbers: numbers ?? [], path: repoPath }),

    createPr: repoPath => gitPost('review/create-pr', { path: repoPath })
  },

  // Repo discovery is a local-disk crawl; on a remote gateway the backend
  // already merges session-derived repos, so this is a no-op.
  scanRepos: async () => []
}

export function desktopGit(): GitBridge | undefined {
  if (typeof window === 'undefined') {
    return undefined
  }

  return isDesktopFsRemoteMode() ? remoteGit : window.beyondDesktop?.git
}
