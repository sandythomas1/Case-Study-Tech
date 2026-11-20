# Security review — static navigation scaffold

Date: 2026-10-30. Independent security-reviewer read-only assessment; Lead synthesis.

## Boundaries
- App renders local preview text and Router links. No authentication, student content, storage, application network calls, backend endpoints, uploads, or service permissions.
- app.json contains only public identity and platform metadata; no environment values or credentials.
- CI uses pull_request on dev, a disposable hosted runner, contents: read, disabled checkout credential persistence, official action commit pins, and no supplied secrets/deployment.
- Preview routes do not grant access to account services. PR #62 must later integrate its own route guards and independent server authorization.

## Dependency advisories — unresolved upstream, contextual LOW

Fresh lockfile audit: **16 affected package entries (13 low, 3 high), representing two underlying advisories**. Zero moderate/critical entries. This is not a clean audit. Installation classification (`--omit=dev`) does not establish client-bundle exposure.

### Zod memory exhaustion

- Advisory: [GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5), upstream HIGH.
- Path: expo 58.0.21 → @expo/cli 58.1.17 → zod 3.25.76.
- CLI Zod sites: `DevToolsPlugin.schema.js` and `createMCPDevToolsExtensionSchema.js`. Plugin descriptors originate from locally installed/autolinked packages. The constrained-array validation sink in `DevToolsPluginCliExtensionResults.js` reads results from a locally spawned installed plugin; MCP extension results are revalidated separately.
- MCP needs `EXPO_UNSTABLE_MCP_SERVER` and `expo-mcp`; this project introduces neither. No installed Expo module configuration declares a devtools plugin. Reviewer found no application or unauthenticated HTTP input path into the vulnerable array validator.
- No demonstrated high exploit path for this shell: reviewer contextual rating LOW, not an assertion that Zod is patched or universally safe. Reassess if developer plugins, MCP, or untrusted configuration become reachable.
- Stable SDK58 CLI still requires Zod ^3.25.76. Latest Zod3 is 3.25.76; fixed 4.6.6 is outside the supported dependency range. A forced major override is unverified and not applied. [Maintainer fix](https://github.com/colinhacks/zod/pull/6652).

### deepmerge prototype poisoning

- Advisory: [GHSA-gcqx-w48m-w2h4](https://github.com/advisories/GHSA-gcqx-w48m-w2h4), LOW, with no published patched release at review time.
- Paths: expo → @expo/config 58.0.9 → deepmerge 4.3.1; jest 30.5.2 → jest-config 30.5.2 → deepmerge 4.3.1.
- Current inputs are repository-controlled Expo/Jest configuration; no student-input merge path. Malicious contributor code in an ordinary unprivileged PR runner already executes within that runner; this workflow provides no deployment credentials.

## Disposition
- No blocking CRITICAL/HIGH finding demonstrated in this scaffold. Both residual contextual LOW findings are documented, not silently waived.
- Keep remediation tracked by #61, including explicit applicability to this lockfile. Do not force npm's proposed legacy Expo/Jest downgrades.
- Adopt a supported SDK58-compatible repair when available; regenerate lockfile and repeat SDK checks, behavior tests, exports, and audit. Reassess before adding data, plugins, externally reachable developer services, or release signing.
- Export scans and platform-specific verification are recorded in verification.md; web-only inspection is not proof about native bundles.
