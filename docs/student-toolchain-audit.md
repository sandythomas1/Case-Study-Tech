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

## Closing re-audit, 2026-11-22

The 2026-11-18 bump is now committed. It is `f514c56` on `feature/4-access-accounts` (PR #62), and the same Expo 58.0.26 tree reached `dev` through #71 (`62462d8`). This section repeats the clean-install audit and the checks the release gate asked for on the committed trees.

Environment: Windows 11, Node 24.11.1, npm 11.19.1 (the version CI uses), uv 0.12.5, Java 25.0.2, firebase-tools 15.18.0. Trees: `origin/dev` at `a365ed4` and `origin/feature/4-access-accounts` at `bfa5066`.

### Audit results

| Tree | Method | High or critical | Moderate |
| --- | --- | --- | --- |
| `dev` `apps/student` | `npm ci`, then `npm audit --json` | 0 | 22 entries, 2 advisories |
| PR #62 `apps/student` | `npm audit --json --package-lock-only` | 0 | 22 entries, 2 advisories |
| PR #62 `infra` | `npm ci`, then `npm audit` | 0 | 0 |

- Installed versions on `dev`: expo 58.0.26, `@expo/cli` 58.1.21, node-forge 1.4.3, braces 3.0.3, minimatch 10.2.6 (root), glob 13.0.6 (root), jest 30.5.2 and jest-expo 58.0.15. PR #62's lockfile resolves the same versions for each of these packages.
- The two advisories this Issue was opened for are closed. node-forge [GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv) affects 1.4.0 and earlier, and 1.4.3 is installed. braces [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm) was withdrawn on 2026-10-23.
- The 22 moderate entries come from the same two advisories the 2026-11-18 section describes: minimatch [GHSA-g3hv-75wg-m249](https://github.com/advisories/GHSA-g3hv-75wg-m249) through `expo` → `@expo/fingerprint`, and glob [GHSA-3g3m-2fjr-6pw4](https://github.com/advisories/GHSA-3g3m-2fjr-6pw4) with minimatch 9 through the Jest 30 coverage chain. Each fix is still a semver-major change outside the declared ranges, so no override was applied.
- npm marks part of the Jest chain as `prod` only because `expo-router` declares an optional peer on `@testing-library/react-native`, which peers on `jest`. `npm explain glob@10.5.0` shows the path. The chain still runs only under `npm test`.

### Checks repeated on the committed trees

| Check | Tree | Result |
| --- | --- | --- |
| `npm ci`, `npm audit --audit-level=high` | `dev` student | Pass (exit 0) |
| `npm run lint`, `npm run typecheck` | `dev` student | Pass |
| `npm test` | `dev` student | 15 of 15 tests, 2 suites |
| `npx expo install --check`, Expo Doctor | `dev` student | Pass, Doctor 20 of 20 |
| `expo export` web, Android and iOS | `dev` student | All three pass |
| Bundle search for `minimatch`, `globparts`, `node-forge` and `braces` | `dev` exports | No package code. The only match is React's "wrap your children in braces" warning text in the web bundle. |
| `uv run pytest`, `ruff check`, `mypy` | `dev` `services/session` | 44 passed, clean, clean |
| Firestore rules tests (`npm --prefix infra test` in the emulator) | PR #62 | 4 of 4 |
| Real-store adapter tests (`test_store_emulator.py` in the emulator) | PR #62 | 5 of 5 |
| CI gate | `dev` `a365ed4`, PR #62 `bfa5066` | Green. Both runs include the high-threshold audit and pip-audit. |

### Limitations

- **No installed native build since the bump.** The last installed Android APK run was on 2026-10-22, before `f514c56`. The bump stayed inside the SDK 58 ranges, but it includes native-code packages: react-native 0.88.1, react-native-screens and react-native-safe-area-context. The JavaScript exports for web, Android and iOS pass, and that proves bundling only, not a native compile. An installed APK or iOS build was not repeated here.
- Real Google sign-in is still unverified on any platform. That gate belongs to #25 and PR #62, not to this audit.
- PR #62's student tree was audited from its lockfile without a separate install. Its own CI run at `bfa5066` installs it and passes.

### Release gate status

Every high and critical finding the gate covers is resolved by a supported in-range update. None of them was declared inapplicable or risk-accepted, and no audit threshold or override changed. Two moderate advisories remain in build and test tooling only, with no in-range upstream fix. They are below the CI gate's threshold, so this is not a clean audit and not a risk acceptance. Adopt the upstream fixes when they ship: `@expo/fingerprint` moving to minimatch 11.0.1 or later, and the Jest coverage chain moving to test-exclude 8. Dependabot does not cover npm in this repository (see [ci-tool-dependabot.md](decisions/ci-tool-dependabot.md)), so check this during dependency updates.
