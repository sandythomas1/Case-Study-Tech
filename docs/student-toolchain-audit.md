# Student toolchain release gate (#61)

Reproduced from `npm ci --no-fund --no-audit` in the isolated short-path checkout on 2026-10-22, using the committed student lockfile, Node 24.11.1 and npm 11.6.2. The clean install added 646 packages; `npm audit --json` then reported 20 high affected dependency entries, zero critical/moderate/low entries. Raw audit and `npm explain braces node-forge --json` output are retained under ignored `tmp/verification/` in the issue-4 worktree, without credentials.

These are propagated dependency entries across two underlying advisories, not 20 unique vulnerabilities:

| Package | Underlying advisory | Affected range | Registry latest observed |
| --- | --- | --- | --- |
| braces | [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm), nested-pattern stack exhaustion | <=3.0.3 | 3.0.3 |
| node-forge | [GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv), RSA signature validation | <=1.4.0 | 1.4.0 |

`npm view` still returns affected latest versions. npm's proposed Expo 44 downgrade is incompatible with the SDK 58/native stack and is not applied. Backend and isolated infrastructure audits being clear do not clear this student/build dependency tree.

The dependency-explanation output identifies Expo/CLI/Metro build-tool paths. A package's presence in the install does not prove execution in the browser/native application bundle. This checkpoint does not claim an absence of runtime exposure, harmless build/signing exposure, or an accepted risk. Build and signing pipelines remain within the release gate; local synthetic verification artifacts are not approved student releases.

Keep #61 open until a supported patched release or an explicitly evidenced inapplicability/mitigation clears every relevant high/critical finding. Then repeat clean-install audit, client checks, native/web builds, emulator authorization tests and the documented release decision. Do not suppress the audit or change its threshold to obtain completion.

## Re-audit, 2026-11-18

Node 24.11.1, npm 11.6.2. Each tree was installed with `npm ci --no-fund --no-audit` from its committed lockfile, then audited with `npm audit --json`. Raw audit JSON (before and after) is in ignored `tmp/verification/2026-11-18/` in this worktree. All counts are affected package entries, not unique vulnerabilities.

### Advisory database changes since 2026-10-22

- braces [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) was **withdrawn** on 2026-10-23. braces 3.0.3 (Metro `metro-file-map` → micromatch) is still installed but is no longer flagged.
- deepmerge [GHSA-gcqx-w48m-w2h4](https://github.com/advisories/GHSA-gcqx-w48m-w2h4) (issue #17 scaffold) was **withdrawn** on 2026-11-16.
- The old lockfiles now also match these advisories:
  - Zod [GHSA-mrhx-c7xc-m3w5](https://github.com/advisories/GHSA-mrhx-c7xc-m3w5): high, fixed in 4.6.6.
  - Four more node-forge advisories, all fixed in 1.4.3: [GHSA-6889-vf6x-f3g5](https://github.com/advisories/GHSA-6889-vf6x-f3g5), [GHSA-w4xr-hqv8-ch44](https://github.com/advisories/GHSA-w4xr-hqv8-ch44), [GHSA-6cv4-p8m7-4r25](https://github.com/advisories/GHSA-6cv4-p8m7-4r25) and [GHSA-j8rw-jp99-435v](https://github.com/advisories/GHSA-j8rw-jp99-435v).
  - glob [GHSA-3g3m-2fjr-6pw4](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4): moderate, fixed in 14.0.2.
  - minimatch [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249): moderate, fixed in 11.0.1.

### Fixed versions inside the SDK 58 ranges

- **Expo.** `expo` 58.0.26, which is inside `~58.0.17`, requires `@expo/cli` ^58.1.21.
  - CLI 58.1.20 and later no longer depend on Zod or glob.
  - The CLI and `@expo/code-signing-certificates` 0.0.7 declare node-forge ^1.4.0, which now resolves to 1.4.3. That clears every node-forge advisory, including [GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv) (affects 1.4.0 and earlier).
  - `@expo/config-plugins` 58.0.13 and `@expo/metro-config` 58.0.23 use tinyglobby instead of glob.
- **Lint tooling.** `eslint` 10.15.0 is inside `^10.13.0` and depends on minimatch ^11.0.5. `typescript-eslint` 8.73.0 is inside `^8.72.0` and depends on minimatch ^11.0.1.
- **No in-range fix for two chains:**
  - `@expo/fingerprint` 0.21.10, the latest release, still pins minimatch ^10.2.6.
  - The Jest 30 coverage chain runs from `babel-plugin-istanbul` 8.0.0 (latest) through `test-exclude` ^7.0.1 to glob 10 and minimatch 9.
  - An override for either would be a semver-major change outside the ranges the SDK and Jest declare, so none was applied.

### Changes applied (working tree, not committed)

**feature/4 `apps/student`** (files: `package.json`, `package-lock.json`)
- Ran `npx expo install --fix`. This raised expo to 58.0.26 and applied SDK-aligned patch and minor bumps: expo-dev-client 58.0.21, expo-linking 58.0.17, expo-router 58.0.32, expo-secure-store 58.0.3, expo-status-bar 58.0.5, react-native 0.88.1, react-native-safe-area-context 5.11.1 and react-native-screens 4.30.1.
- Ran `npm update eslint typescript-eslint @eslint/js`, which changed only the lockfile.
- npm also rewrote `package.json` into its standard 2-space format.
- Expo asked to add an `expo-status-bar` plugin entry to `app.config.ts`. It was not added: with no props the plugin does nothing.

**feature/17 `apps/student`** (files: `package.json`, `package-lock.json`)
- Ran the same `npx expo install --fix`, which also raised jest-expo to 58.0.15, and the same `npm update`.
- Expo wrote an `expo-status-bar` plugin entry into `app.json`. It was reverted for the same reason.

No `npm audit fix --force`, Expo or Firebase downgrade, or new override was used. The feature/4 `infra` harness was not changed. It still audits at 0 with its grpc-js 1.14.6 override.

### Counts

| Tree | Before (clean install, 2026-11-18) | After |
| --- | --- | --- |
| feature/4 `apps/student` | 17 entries: 3 high (`@expo/cli`, node-forge, zod) and 14 moderate | 3 moderate entries (`expo`, `@expo/fingerprint`, minimatch). 1 advisory. 0 high or critical |
| feature/4 `infra` | 0 | 0 (unchanged) |
| feature/17 `apps/student` | 35 entries: 2 high (`@expo/cli`, zod) and 33 moderate | 22 moderate entries. 2 advisories (minimatch, glob). 0 high or critical |

### Verification after the change

- **feature/4.** `npx expo install --check` reports dependencies up to date. Expo Doctor passes 20/20. `tsc --noEmit` and `eslint .` pass. Vitest passes 12/12. `expo export` succeeds for web, Android and iOS.
- **feature/17.** `npx expo install --check` is clean. Expo Doctor passes 20/20. Typecheck and lint pass. Jest passes 15/15 across 2 suites. `expo export` succeeds for web, Android and iOS.
- **Not re-run:** emulator rules and real-store tests, backend pytest and pip-audit, and installed native or device builds. Infra and the backend did not change. The student dependency bump still needs the emulator, real-store and installed-device runs before a release decision.

### Reachability

- **Cleared findings** (node-forge, Zod, glob in `@expo/cli`) were build, signing and dev-server tooling. They are now resolved, so their exposure no longer needs to be argued.
- **minimatch GHSA-g3hv-75wg-m249** reaches the app through `expo` → `@expo/fingerprint`. This is build-time tooling:
  - `expo` reaches it only from `bin/fingerprint` and the Node-only `expo/fingerprint` subpath. The app source imports neither.
  - Fingerprinting hashes repository-controlled native project files.
  - A search of the web, Android and iOS exports from both trees for `minimatch`, `globparts`, `braceExpand`, `test-exclude` and `node-forge` found no matches.
- **glob GHSA-3g3m-2fjr-6pw4, and minimatch through Jest 30 coverage** (feature/17 only): test-only tooling that runs on repository-controlled patterns.
- **Shipped bundle:** no flagged package was found in the exported web or native bundles.

### Residual risk

No high or critical advisory remains in either student tree. Moderate denial-of-service and cancellation-bypass advisories remain in build and test tooling. They have no in-range upstream fix, and their inputs come from the repository. This is not a clean audit and not a risk acceptance.

Adopt the fixes when they ship:
- `@expo/fingerprint` moves to minimatch 11.0.1 or later.
- The Jest coverage chain moves to test-exclude 8.

The #61 release gate stays open until two things happen: the bump is committed, and the emulator, real-store and native checks are repeated on it.
