import { contextBridge, ipcRenderer, webFrame, webUtils } from 'electron'

import type { DesktopProfileRoute } from './desktop-profile'
import type { HudModifierApi, HudModifierStatus } from './hud-modifier-types'
import { customWindowControlsEnabled } from './window-controls'

// Which translucency the OS can back. Asked synchrobeyondly because the renderer
// needs it before its first paint, and answered by main because deciding it
// needs `os.release()` — a sandboxed preload may only require electron, events,
// timers and url, so importing node:os here throws before contextBridge runs
// and takes the ENTIRE bridge down with it (window.beyondDesktop undefined =>
// "Desktop IPC bridge is unavailable"). No reply means no glass, which degrades
// to an ordinary opaque window rather than a page thinned over nothing.
const translucencySupport = ipcRenderer.sendSync('beyond:translucency:support')
const hudWindowing = ipcRenderer.sendSync('beyond:hud:windowing')
const hudNativeDrag = hudWindowing?.nativeDrag === true

const launchFlags: { localModels?: boolean; assumeFreshInstall?: boolean } | undefined =
  ipcRenderer.sendSync('beyond:feature-flags')

// Local, sanitized skin payload for the first renderer theme paint. This does
// not wait on `gateway.ready`, so an unreachable remote primary cannot force
// the built-in palette over the skin configured on this machine.
const localSkin = ipcRenderer.sendSync('beyond:skin:local')

import { unwrapExpectedNotFound } from './api-expected-404'

contextBridge.exposeInMainWorld('beyondDesktop', {
  glassSupported: translucencySupport?.glass === true,
  translucencySupported: translucencySupport?.translucency === true,
  // Launch-flag fact: the app was started with --local, so the renderer may
  // show the local-models surfaces. Static for the window's lifetime.
  localModelsEnabled: launchFlags?.localModels === true,
  // Dev-only launch fact: an unpackaged app started with --fresh-install, so
  // onboarding treats this launch as a fresh install. Always false when packaged.
  assumeFreshInstall: launchFlags?.assumeFreshInstall === true,
  localSkin: localSkin && typeof localSkin === 'object' ? localSkin : null,
  getConnection: (profile, opts) => ipcRenderer.invoke('beyond:connection', profile, opts),
  // Loopback origin that hosts YouTube's player for the file:// renderer.
  getEmbedHostOrigin: () => ipcRenderer.invoke('beyond:embed-host:origin'),
  // Registry-scoped backend resolution: { connectionId, profile } → descriptor.
  getConnectionFor: payload => ipcRenderer.invoke('beyond:connection:for', payload),
  getProfileRoutes: profiles => ipcRenderer.invoke('beyond:plugin-profile-routes', profiles),
  revalidateConnection: () => ipcRenderer.invoke('beyond:connection:revalidate'),
  getGatewayWsUrl: profile => ipcRenderer.invoke('beyond:gateway:ws-url', profile),
  // Registry-scoped fresh WS URL: { connectionId, profile } → result shape of
  // getGatewayWsUrl, minted against that connection's backend.
  getGatewayWsUrlFor: payload => ipcRenderer.invoke('beyond:gateway:ws-url-for', payload),
  // { connectionId, profile, pluginId, path } → one-use local plugin socket URL, null, or { refused: 'permission' }.
  getPluginWsUrl: payload => ipcRenderer.invoke('beyond:plugin:ws-url', payload),
  // Union agent roster across every registered connection.
  getAgentRoster: () => ipcRenderer.invoke('beyond:agents:roster'),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('beyond:window:openSession', sessionId, opts),
  openSessionInTerminal: (sessionId, opts) => ipcRenderer.invoke('beyond:window:openInTerminal', sessionId, opts),
  openWindow: (options?: DesktopProfileRoute) => ipcRenderer.invoke('beyond:window:openInstance', options),
  openBrowserWindow: tabId => ipcRenderer.invoke('beyond:window:openBrowser', tabId),
  windowRelay: {
    send: payload => ipcRenderer.send('beyond:window:relay', payload),
    onMessage: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('beyond:window:relay', listener)

      return () => ipcRenderer.removeListener('beyond:window:relay', listener)
    }
  },
  onBrowserPopoutClosed: callback => {
    const listener = (_event, tabId) => callback(tabId)
    ipcRenderer.on('beyond:browser-popout:closed', listener)

    return () => ipcRenderer.removeListener('beyond:browser-popout:closed', listener)
  },
  claimAmbientCue: key => ipcRenderer.invoke('beyond:ambient:claim', key),
  windowControls: {
    custom: customWindowControlsEnabled(),
    minimize: () => ipcRenderer.send('beyond:window-control', 'minimize'),
    toggleMaximize: () => ipcRenderer.send('beyond:window-control', 'toggle-maximize'),
    close: () => ipcRenderer.send('beyond:window-control', 'close')
  },
  wakeIndicator: {
    getState: () => ipcRenderer.invoke('beyond:wake-indicator:get'),
    setState: state => ipcRenderer.send('beyond:wake-indicator:set', state),
    onState: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('beyond:wake-indicator:state', listener)

      return () => ipcRenderer.removeListener('beyond:wake-indicator:state', listener)
    }
  },
  chatOnboarding: {
    size: mode => ipcRenderer.send('beyond:window:size', mode)
  },
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('beyond:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('beyond:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('beyond:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('beyond:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('beyond:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('beyond:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('beyond:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('beyond:pet-overlay:state', listener)

      return () => ipcRenderer.removeListener('beyond:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('beyond:pet-overlay:control', listener)

      return () => ipcRenderer.removeListener('beyond:pet-overlay:control', listener)
    }
  },
  // HUD mode: the chrome-free floating chat. A full app renderer (own gateway)
  // sized as a floating bar, so it mounts the real composer. Main owns the
  // window; `onChanged` keeps every window's toggle truthful.
  hud: {
    nativeDrag: hudNativeDrag,
    windowing: {
      clientPlacement: hudWindowing?.clientPlacement !== false,
      controlDrag: hudWindowing?.controlDrag === true,
      nativeDrag: hudNativeDrag,
      solid: hudWindowing?.solid === true,
      workspaceTransfer: hudWindowing?.workspaceTransfer === true
    },
    open: request => ipcRenderer.invoke('beyond:hud:open', request),
    close: () => ipcRenderer.invoke('beyond:hud:close'),
    setIgnoreMouse: ignore => ipcRenderer.send('beyond:hud:ignore-mouse', ignore),
    beginMove: () => ipcRenderer.send('beyond:hud:begin-move'),
    endMove: () => ipcRenderer.send('beyond:hud:end-move'),
    moveBy: delta => ipcRenderer.send('beyond:hud:move-by', delta),
    setWorkspaceTransfer: transferring => ipcRenderer.send('beyond:hud:workspace-transfer', transferring),
    setBounds: bounds => ipcRenderer.send('beyond:hud:set-bounds', bounds),
    resetLayout: () => ipcRenderer.invoke('beyond:hud:reset-layout'),
    // Whether the band covers the window below the bar. Main pairs it with the
    // user's translucency setting to decide the native frost (macOS vibrancy /
    // Windows 11 DWM backdrop) — see hudFrostFor.
    setFrost: showing => ipcRenderer.invoke('beyond:hud:frost', showing),
    // The HUD tells main which session it is on; main hands that back to the
    // app window when the HUD closes, so the app can re-home onto it.
    setSession: sessionId => ipcRenderer.send('beyond:hud:session', sessionId),
    onGoto: callback => {
      const listener = (_event, sessionId) => callback(sessionId)
      ipcRenderer.on('beyond:hud:goto', listener)

      return () => ipcRenderer.removeListener('beyond:hud:goto', listener)
    },
    onChanged: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('beyond:hud:changed', listener)

      return () => ipcRenderer.removeListener('beyond:hud:changed', listener)
    },
    // Linux only, and silent elsewhere: where the cursor is, in page
    // coordinates, or null when it has left the window. Stands in for the
    // mousemove that `setIgnoreMouseEvents(true, { forward: true })` delivers on
    // macOS and Windows but not here.
    onCursor: callback => {
      const listener = (_event, point) => callback(point)
      ipcRenderer.on('beyond:hud:cursor', listener)

      return () => ipcRenderer.removeListener('beyond:hud:cursor', listener)
    },
    // Main's game-overlay watch: whether a fullscreen app (a game) is under
    // the HUD, so the renderer can step back to the low-opacity overlay
    // treatment while one owns the screen.
    onGameOverlay: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('beyond:hud:game-overlay', listener)

      return () => ipcRenderer.removeListener('beyond:hud:game-overlay', listener)
    }
  },
  hudModifier: {
    getSettings: () => ipcRenderer.invoke('beyond:hud-modifier:settings:get'),
    setEnabled: enabled => ipcRenderer.invoke('beyond:hud-modifier:settings:set', enabled),
    openPermissionSettings: () => ipcRenderer.invoke('beyond:hud-modifier:permission'),
    onStatus: callback => {
      const listener = (_event: Electron.IpcRendererEvent, status: HudModifierStatus) => callback(status)
      ipcRenderer.on('beyond:hud-modifier:status', listener)

      return () => ipcRenderer.removeListener('beyond:hud-modifier:status', listener)
    }
  } satisfies HudModifierApi,
  // macOS native screenshot gesture; captures require a main-issued request.
  screenshot:
    process.platform === 'darwin'
      ? {
          getSettings: () => ipcRenderer.invoke('beyond:screenshot:settings:get'),
          setEnabled: enabled => ipcRenderer.invoke('beyond:screenshot:settings:set', enabled),
          openPermissionSettings: kind => ipcRenderer.invoke('beyond:screenshot:permission', kind),
          capture: requestId => ipcRenderer.invoke('beyond:screenshot:capture', requestId),
          onStatus: callback => {
            const listener = (_event, status) => callback(status)
            ipcRenderer.on('beyond:screenshot:status', listener)

            return () => ipcRenderer.removeListener('beyond:screenshot:status', listener)
          },
          onRequest: callback => {
            const channel = 'beyond:screenshot:request'
            const listener = (_event, requestId) => callback(requestId)

            if (ipcRenderer.listenerCount(channel) === 0) {
              ipcRenderer.send('beyond:screenshot:subscribe', true)
            }

            ipcRenderer.on(channel, listener)

            return () => {
              ipcRenderer.removeListener(channel, listener)

              if (ipcRenderer.listenerCount(channel) === 0) {
                ipcRenderer.send('beyond:screenshot:subscribe', false)
              }
            }
          }
        }
      : undefined,
  // Quick Entry: the global-hotkey mini composer window. Main owns the OS
  // shortcut + the persisted preference; the quick window only captures text
  // and hands it back, and the primary renderer submits it through the normal
  // prompt path.
  quickEntry: {
    getSettings: () => ipcRenderer.invoke('beyond:quick-entry:settings:get'),
    setSettings: patch => ipcRenderer.invoke('beyond:quick-entry:settings:set', patch),
    // Invoke returns the delivery result so the draft is not lost (#85590).
    submit: payload => ipcRenderer.invoke('beyond:quick-entry:submit', payload),
    // Main cannot invoke the primary renderer, so it receives this ack (#85590).
    ackSubmit: (correlationId, result) => ipcRenderer.send('beyond:quick-entry:ack', { correlationId, result }),
    dismiss: () => ipcRenderer.send('beyond:quick-entry:dismiss'),
    // Primary renderer → main → quick window: gateway connection state + the
    // recent-session options the target picker offers. Main caches the latest
    // payload so a freshly spawned quick window starts from truth.
    pushState: payload => ipcRenderer.send('beyond:quick-entry:state', payload),
    // Quick window subscribes to those pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('beyond:quick-entry:state', listener)

      return () => ipcRenderer.removeListener('beyond:quick-entry:state', listener)
    },
    // Main → primary renderer: a submit captured by the quick window.
    onSubmit: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('beyond:quick-entry:submit', listener)

      return () => ipcRenderer.removeListener('beyond:quick-entry:submit', listener)
    },
    // Main → quick window: you were just summoned (reset draft + refocus).
    onShown: callback => {
      const listener = () => callback()
      ipcRenderer.on('beyond:quick-entry:shown', listener)

      return () => ipcRenderer.removeListener('beyond:quick-entry:shown', listener)
    },
    // Main → quick window: the outcome of a submit whose relay already timed
    // out. Delivery is now KNOWN — reconcile the unknown state instead of
    // leaving the user to resend a prompt that may already be delivered.
    onLateResult: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('beyond:quick-entry:late-result', listener)

      return () => ipcRenderer.removeListener('beyond:quick-entry:late-result', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('beyond:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('beyond:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('beyond:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('beyond:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('beyond:connection-config:test', payload),
  // Opt-in OS-keychain encryption for stored gateway secrets (default off —
  // see secret-storage-policy.ts). get never touches the OS keychain.
  getSecretStorageEncryption: () => ipcRenderer.invoke('beyond:secret-storage:get'),
  setSecretStorageEncryption: (on: boolean) => ipcRenderer.invoke('beyond:secret-storage:set', on),
  // v2 multi-connection registry: named agent sources (local / remote / cloud / ssh).
  connections: {
    list: () => ipcRenderer.invoke('beyond:connections:list'),
    save: payload => ipcRenderer.invoke('beyond:connections:save', payload),
    remove: id => ipcRenderer.invoke('beyond:connections:remove', id),
    setPrimary: id => ipcRenderer.invoke('beyond:connections:set-primary', id),
    setLaunchMode: mode => ipcRenderer.invoke('beyond:connections:set-launch-mode', mode),
    setLastUsed: id => ipcRenderer.invoke('beyond:connections:set-last-used', id),
    test: id => ipcRenderer.invoke('beyond:connections:test', id),
    updateManaged: id => ipcRenderer.invoke('beyond:connections:update-managed', id),
    // Fan out `beyond update` to every eligible registered connection.
    // Optional excludeIds skips rows the caller updates through another path.
    updateAll: options => ipcRenderer.invoke('beyond:connections:update-all', options),
    // Registry lifecycle push (main → renderer): a connection was removed or
    // materially edited, so secondaries scoped to it must be disposed (and,
    // for edits, re-dialed at the new target).
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('beyond:connections:changed', listener)

      return () => ipcRenderer.removeListener('beyond:connections:changed', listener)
    }
  },
  sshConfigHosts: () => ipcRenderer.invoke('beyond:ssh-config:hosts'),
  sshResolveHost: host => ipcRenderer.invoke('beyond:ssh-config:resolve', host),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('beyond:connection-config:probe', remoteUrl),
  // `options` lets a registry-editor draft sign in BEFORE it is saved: the
  // main process settles the draft's connection id up front so the login
  // window writes into the per-connection cookie jar the saved entry will
  // read (not the legacy shared jar an unsaved URL would fall back to).
  oauthLoginConnectionConfig: (remoteUrl, options) =>
    ipcRenderer.invoke('beyond:connection-config:oauth-login', remoteUrl, options),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('beyond:connection-config:oauth-logout', remoteUrl),
  // Beyond Cloud: one portal login powers discovery + silent per-agent sign-in
  // (cloud-auto-discovery Phase 3).
  cloud: {
    status: () => ipcRenderer.invoke('beyond:cloud:status'),
    login: () => ipcRenderer.invoke('beyond:cloud:login'),
    logout: () => ipcRenderer.invoke('beyond:cloud:logout'),
    discover: org => ipcRenderer.invoke('beyond:cloud:discover', org),
    agentSignIn: dashboardUrl => ipcRenderer.invoke('beyond:cloud:agent-sign-in', dashboardUrl)
  },
  profile: {
    getDefault: () => ipcRenderer.invoke('beyond:profile:default:get'),
    setDefault: (route: DesktopProfileRoute) => ipcRenderer.invoke('beyond:profile:default:set', route),
    onDefaultChanged: (callback: (route: DesktopProfileRoute | null) => void) => {
      const listener = (_event: Electron.IpcRendererEvent, route: DesktopProfileRoute | null) => callback(route)
      ipcRenderer.on('beyond:profile:default:changed', listener)

      return () => ipcRenderer.removeListener('beyond:profile:default:changed', listener)
    },
    get: () => ipcRenderer.invoke('beyond:profile:get'),
    remember: name => ipcRenderer.invoke('beyond:profile:remember', name),
    set: name => ipcRenderer.invoke('beyond:profile:set', name)
  },
  // The handler resolves an expected 404 with a sentinel instead of rejecting
  // (Electron logs a stack for every rejected invoke). Turn it back into the
  // rejection the renderer expects — see electron/api-expected-404.ts.
  api: request => ipcRenderer.invoke('beyond:api', request).then(unwrapExpectedNotFound),
  notify: payload => ipcRenderer.invoke('beyond:notify', payload),
  claimStartupLatency: () => ipcRenderer.invoke('beyond:startup-latency:claim'),
  requestMicrophoneAccess: () => ipcRenderer.invoke('beyond:requestMicrophoneAccess'),
  readWindowBelow: () => ipcRenderer.invoke('beyond:window:readBelow'),
  readFileDataUrl: filePath => ipcRenderer.invoke('beyond:readFileDataUrl', filePath),
  readFileDataUrlForAttach: filePath => ipcRenderer.invoke('beyond:readFileDataUrlForAttach', filePath),
  dataUrlReadMax: {
    get: () => ipcRenderer.invoke('beyond:data-url-read-max:get'),
    set: maxMb => ipcRenderer.invoke('beyond:data-url-read-max:set', maxMb)
  },
  readFileText: filePath => ipcRenderer.invoke('beyond:readFileText', filePath),
  readPluginSource: (filePath: string) => ipcRenderer.invoke('beyond:readPluginSource', filePath),
  selectPaths: options => ipcRenderer.invoke('beyond:selectPaths', options),
  selectSavePath: options => ipcRenderer.invoke('beyond:selectSavePath', options),
  saveTextFileAs: request => ipcRenderer.invoke('beyond:saveTextFileAs', request),
  writeClipboard: text => ipcRenderer.invoke('beyond:writeClipboard', text),
  readClipboard: () => ipcRenderer.invoke('beyond:readClipboard'),
  saveGatewayFile: payload => ipcRenderer.invoke('beyond:saveGatewayFile', payload),
  saveImageFromUrl: url => ipcRenderer.invoke('beyond:saveImageFromUrl', url),
  contextMenuEdit: command => ipcRenderer.invoke('beyond:context-menu:edit', command),
  contextMenuCopyImage: () => ipcRenderer.invoke('beyond:context-menu:copy-image'),
  contextMenuSpellcheck: action => ipcRenderer.invoke('beyond:context-menu:spellcheck', action),
  contextMenuGuestAddWord: payload => ipcRenderer.invoke('beyond:context-menu:guest-add-word', payload),
  spellcheckDictionary: (op, word) => ipcRenderer.invoke('beyond:spellcheck:dictionary', { op, word }),
  onContextMenuSpellcheck: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('beyond:context-menu-spellcheck', listener)

    return () => ipcRenderer.removeListener('beyond:context-menu-spellcheck', listener)
  },
  saveImageBuffer: (data, ext, name) => ipcRenderer.invoke('beyond:saveImageBuffer', { data, ext, name }),
  capturePreview: payload => ipcRenderer.invoke('beyond:capturePreview', payload),
  savePastedText: text => ipcRenderer.invoke('beyond:savePastedText', { text }),
  saveClipboardImage: () => ipcRenderer.invoke('beyond:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('beyond:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('beyond:watchPreviewFile', url),
  watchDirectory: dir => ipcRenderer.invoke('beyond:watchDirectory', dir),
  stopPreviewFileWatch: id => ipcRenderer.invoke('beyond:stopPreviewFileWatch', id),
  setActiveWork: payload => ipcRenderer.send('beyond:active-work', payload),
  setTitleBarTheme: payload => ipcRenderer.send('beyond:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('beyond:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('beyond:translucency', payload),
  setKeepAwake: mode => ipcRenderer.send('beyond:keep-awake', mode),
  // Once per computer, after a timed sleep interrupted a turn with keep-awake off.
  onKeepAwakeOffer: callback => {
    const listener = () => callback()
    ipcRenderer.on('beyond:keep-awake-offer', listener)

    return () => ipcRenderer.removeListener('beyond:keep-awake-offer', listener)
  },
  minimizeToTray: {
    get: () => ipcRenderer.invoke('beyond:minimize-to-tray:get'),
    set: on => ipcRenderer.invoke('beyond:minimize-to-tray:set', on),
    onChanged: callback => {
      const listener = (_event, status) => callback(status)
      ipcRenderer.on('beyond:minimize-to-tray:changed', listener)

      return () => ipcRenderer.removeListener('beyond:minimize-to-tray:changed', listener)
    }
  },
  setDisableF12: blocked => ipcRenderer.send('beyond:devtools:disable-f12', blocked),
  setF12ShortcutActive: active => ipcRenderer.send('beyond:f12ShortcutActive', Boolean(active)),
  onF12Shortcut: callback => {
    const listener = (_event, input) => callback(input)
    ipcRenderer.on('beyond:f12-shortcut', listener)

    return () => ipcRenderer.removeListener('beyond:f12-shortcut', listener)
  },
  setPreviewShortcutActive: active => ipcRenderer.send('beyond:previewShortcutActive', Boolean(active)),
  setPreviewGuestHidden: (webContentsId, hidden) =>
    ipcRenderer.send('beyond:preview-guest-hidden', { webContentsId, hidden: Boolean(hidden) }),
  openExternal: url => ipcRenderer.invoke('beyond:openExternal', url),
  freeTierChallenge: {
    // Load the account service's challenge page in a hidden window (revealed
    // only if the page asks for the human). Resolves with how it ended.
    run: request => ipcRenderer.invoke('beyond:freeTierChallenge:run', request)
  },
  mcpOauth: {
    // One-shot loopback listener for MCP OAuth against remote backends: bind
    // on this machine, hand redirectUri to mcp.servers.oauth.start, then wait
    // for the provider redirect and relay code/state via oauth.callback.
    listen: () => ipcRenderer.invoke('beyond:mcp-oauth:listen'),
    wait: (id, timeoutMs) => ipcRenderer.invoke('beyond:mcp-oauth:wait', id, timeoutMs),
    cancel: id => ipcRenderer.invoke('beyond:mcp-oauth:cancel', id)
  },
  openPreviewInBrowser: url => ipcRenderer.invoke('beyond:openPreviewInBrowser', url),
  reachPreviewUrl: url => ipcRenderer.invoke('beyond:preview:reach', url),
  setActiveConnectionRoute: route => ipcRenderer.send('beyond:connection:active-route', route),
  fetchLinkTitle: url => ipcRenderer.invoke('beyond:fetchLinkTitle', url),
  resolveFavicon: url => ipcRenderer.invoke('beyond:resolveFavicon', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('beyond:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('beyond:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('beyond:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('beyond:setting:defaultProjectDir:pick')
  },
  preparedSubmissions: {
    read: () => ipcRenderer.invoke('beyond:prepared-submissions:read'),
    update: (key, entry) => ipcRenderer.invoke('beyond:prepared-submissions:update', key, entry),
    compareAndSet: (key, expected, entry) =>
      ipcRenderer.invoke('beyond:prepared-submissions:compare-and-set', key, expected, entry)
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('beyond:zoom:get'),
    // Synchrobeyond zoom factor (1 = 100%). Coordinate math needs it in the
    // same tick as the event it converts, so no IPC round-trip here.
    factor: () => webFrame.getZoomFactor(),
    setPercent: percent => ipcRenderer.send('beyond:zoom:set-percent', percent),
    // Fires on every zoom change, including the Ctrl/Cmd +/-/0 shortcuts,
    // so the settings UI can stay in sync with the keyboard.
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('beyond:zoom:changed', listener)

      return () => ipcRenderer.removeListener('beyond:zoom:changed', listener)
    }
  },
  revealLogs: () => ipcRenderer.invoke('beyond:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('beyond:logs:recent'),
  // Fire-and-forget: persists a renderer error-boundary catch (with component
  // stack) to desktop.log so crashes survive the window (#79428).
  reportRendererError: report => ipcRenderer.send('beyond:logs:renderer-error', report),
  logLine: (line: string): void => ipcRenderer.send('beyond:logs:renderer-line', line),
  readDir: dirPath => ipcRenderer.invoke('beyond:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('beyond:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('beyond:fs:reveal', targetPath),
  openDir: dirPath => ipcRenderer.invoke('beyond:fs:openDir', dirPath),
  desktopPluginsRoot: () => ipcRenderer.invoke('beyond:fs:desktopPluginsRoot'),
  reconcileDesktopPlugins: () => ipcRenderer.invoke('beyond:fs:reconcileDesktopPlugins'),
  logsRoot: (profile?: string) => ipcRenderer.invoke('beyond:fs:logsRoot', profile),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('beyond:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('beyond:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('beyond:fs:trash', targetPath),
  pluginFiles: {
    request: (pluginId, labels) => ipcRenderer.invoke('beyond:pluginFiles:request', pluginId, labels),
    grants: pluginId => ipcRenderer.invoke('beyond:pluginFiles:grants', pluginId),
    revoke: (pluginId, folderId) => ipcRenderer.invoke('beyond:pluginFiles:revoke', pluginId, folderId),
    op: (pluginId, request) => ipcRenderer.invoke('beyond:pluginFiles:op', pluginId, request),
    onChanged: callback => {
      const listener = (_event, change) => callback(change)
      ipcRenderer.on('beyond:pluginFiles:changed', listener)

      return () => ipcRenderer.removeListener('beyond:pluginFiles:changed', listener)
    }
  },
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('beyond:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('beyond:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('beyond:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('beyond:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('beyond:git:branchList', repoPath),
    baseBranchList: repoPath => ipcRenderer.invoke('beyond:git:baseBranchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('beyond:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('beyond:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('beyond:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('beyond:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('beyond:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('beyond:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('beyond:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('beyond:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('beyond:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('beyond:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('beyond:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('beyond:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('beyond:git:review:shipInfo', repoPath),
      prList: (repoPath, branches, numbers) =>
        ipcRenderer.invoke('beyond:git:review:prList', repoPath, branches, numbers),
      createPr: repoPath => ipcRenderer.invoke('beyond:git:review:createPr', repoPath)
    }
  },
  terminal: {
    attach: id => ipcRenderer.invoke('beyond:terminal:attach', id),
    cwd: id => ipcRenderer.invoke('beyond:terminal:cwd', id),
    dispose: id => ipcRenderer.invoke('beyond:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('beyond:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('beyond:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('beyond:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `beyond:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `beyond:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('beyond:close-preview-requested', listener)

    return () => ipcRenderer.removeListener('beyond:close-preview-requested', listener)
  },
  onPreviewNav: callback => {
    const listener = (_event, command) => callback(command)
    ipcRenderer.on('beyond:preview-nav', listener)

    return () => ipcRenderer.removeListener('beyond:preview-nav', listener)
  },
  onOpenFolderRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('beyond:open-folder-requested', listener)

    return () => ipcRenderer.removeListener('beyond:open-folder-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('beyond:open-updates', listener)

    return () => ipcRenderer.removeListener('beyond:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('beyond:deep-link', listener)

    return () => ipcRenderer.removeListener('beyond:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('beyond:deep-link-ready'),
  probePluginRepo: payload => ipcRenderer.invoke('beyond:plugin:probe', payload),
  installDesktopPlugin: payload => ipcRenderer.invoke('beyond:plugin:installDesktop', payload),
  removeDesktopPlugin: payload => ipcRenderer.invoke('beyond:plugin:removeDesktop', payload),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('beyond:window-state-changed', listener)

    return () => ipcRenderer.removeListener('beyond:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('beyond:focus-session', listener)

    return () => ipcRenderer.removeListener('beyond:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('beyond:notification-action', listener)

    return () => ipcRenderer.removeListener('beyond:notification-action', listener)
  },
  onNotificationActivate: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('beyond:notification-activate', listener)

    return () => ipcRenderer.removeListener('beyond:notification-activate', listener)
  },
  onExternalOpenFailed: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('beyond:external-open-failed', listener)

    return () => ipcRenderer.removeListener('beyond:external-open-failed', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('beyond:preview-file-changed', listener)

    return () => ipcRenderer.removeListener('beyond:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('beyond:backend-exit', listener)

    return () => ipcRenderer.removeListener('beyond:backend-exit', listener)
  },
  // Soft gateway-mode apply finished tearing down the primary backend. Renderer
  // should wipe session lists + re-dial without a window reload.
  onConnectionApplied: callback => {
    const listener = () => callback()
    ipcRenderer.on('beyond:connection:applied', listener)

    return () => ipcRenderer.removeListener('beyond:connection:applied', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('beyond:power-resume', listener)

    return () => ipcRenderer.removeListener('beyond:power-resume', listener)
  },
  // AC ↔ battery transitions; renderers slow their backstop polls on battery.
  getOnBattery: () => ipcRenderer.invoke('beyond:power-battery:get'),
  onBatteryChanged: callback => {
    const listener = (_event, onBattery) => callback(Boolean(onBattery))
    ipcRenderer.on('beyond:power-battery', listener)

    return () => ipcRenderer.removeListener('beyond:power-battery', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('beyond:boot-progress', listener)

    return () => ipcRenderer.removeListener('beyond:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.ts (apps/desktop/electron/bootstrap-runner.ts).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('beyond:bootstrap:get'),
  probeLocalBackend: () => ipcRenderer.invoke('beyond:local-backend:probe'),
  continueBootstrapLocal: () => ipcRenderer.invoke('beyond:bootstrap:continue-local'),
  recycleBackend: profile => ipcRenderer.invoke('beyond:backend:recycle', profile),
  resetBootstrap: () => ipcRenderer.invoke('beyond:bootstrap:reset'),
  updateHold: {
    recheck: () => ipcRenderer.invoke('beyond:update-hold:recheck'),
    quit: () => ipcRenderer.invoke('beyond:update-hold:quit'),
    startAnyway: (request: { holdId: string; confirmed: true }) =>
      ipcRenderer.invoke('beyond:update-hold:start-anyway', request)
  },
  repairBootstrap: () => ipcRenderer.invoke('beyond:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('beyond:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('beyond:bootstrap:event', listener)

    return () => ipcRenderer.removeListener('beyond:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('beyond:version'),
  relaunchApp: () => ipcRenderer.invoke('beyond:app:relaunch'),
  getMachineProfile: () => ipcRenderer.invoke('beyond:machine:profile'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('beyond:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('beyond:uninstall:summary'),
    run: mode => ipcRenderer.invoke('beyond:uninstall:run', { mode }),
    openAppsSettings: () => ipcRenderer.invoke('beyond:uninstall:openAppsSettings')
  },
  updates: {
    check: opts => ipcRenderer.invoke('beyond:updates:check', opts),
    apply: opts => ipcRenderer.invoke('beyond:updates:apply', opts),
    setChannel: name => ipcRenderer.invoke('beyond:updates:channel:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('beyond:updates:progress', listener)

      return () => ipcRenderer.removeListener('beyond:updates:progress', listener)
    },
    takePendingRun: () => ipcRenderer.invoke('beyond:updates:metric:take'),
    ackPendingRun: sent => ipcRenderer.invoke('beyond:updates:metric:ack', sent),
    onPendingRun: callback => {
      const listener = () => callback()
      ipcRenderer.on('beyond:updates:metric:pending', listener)

      return () => ipcRenderer.removeListener('beyond:updates:metric:pending', listener)
    }
  },
  desktopMetrics: {
    setEnabled: (on, profile) => ipcRenderer.invoke('beyond:desktop-metrics:set-enabled', on, profile),
    takeRendererCrashes: () => ipcRenderer.invoke('beyond:desktop-metrics:crash:take'),
    ackRendererCrashes: sent => ipcRenderer.invoke('beyond:desktop-metrics:crash:ack', sent)
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('beyond:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('beyond:vscode-theme:search', query)
  },
  // Find-in-page (Ctrl/Cmd+F): delegates to Electron's
  // webContents.findInPage on the IPC sender's window so a Cmd+F pressed
  // in a secondary session window searches THAT window, not the primary.
  // `onFoundInPage` returns the unsubscribe fn; the renderer wires it via
  // `initFindInPageListener` in store/find-in-page.ts and tears it down
  // when the FindBar unmounts.
  findInPage: (query, options) => ipcRenderer.invoke('beyond:find-in-page', query, options),
  stopFindInPage: () => ipcRenderer.invoke('beyond:stop-find-in-page'),
  onFoundInPage: callback => {
    const listener = (_event, result) => callback(result)
    ipcRenderer.on('beyond:found-in-page', listener)

    return () => ipcRenderer.removeListener('beyond:found-in-page', listener)
  },
  // Main-process `before-input-event` forwards Ctrl/Cmd+F here so renderer
  // can open the FindBar even when the GTK compositor has already grabbed
  // the chord at the windowing layer (#81727).
  onOpenFindBarRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('beyond:open-find-bar', listener)

    return () => ipcRenderer.removeListener('beyond:open-find-bar', listener)
  }
})
