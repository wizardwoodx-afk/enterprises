// data-paths.ts — typed re-export of the shared pure resolver in data-paths.mjs.
// The app imports these names here (extensionless, for the tsc/esbuild build);
// the CI smoke driver imports the .mjs directly because Node's type-stripping
// cannot resolve extensionless TypeScript imports.
export { platformDefaultBeyondHome, resolveDesktopBeyondHome, resolveDesktopUserData } from './data-paths.mjs'
export type { BeyondHomeOptions } from './data-paths.mjs'
