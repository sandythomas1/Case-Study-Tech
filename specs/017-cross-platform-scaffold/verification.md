# Verification — issue #17 scaffold

Date: 2026-10-30. Worktree C:/cst17, branch feature/17-cross-platform-scaffold, base dev aa6ea60.

## Acceptance criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| AC1: web, Android emulator, iOS simulator start from the same project and show the shell | PARTIAL | Actual web navigation verified. Android result below. No Mac/Xcode simulator available, so iOS runtime remains unverified and the issue checkbox remains unchecked. |
| AC2: lint, strict typecheck and unit tests pass from clean checkout/install | PASS | Fresh npm ci; lint/typecheck; final 15 tests in two suites. SDK compatibility and Expo Doctor pass. |
| AC3: client bundle contains no secrets | PASS, bounded review | Public-only static app.json, no application environment/network/storage code; source plus web/Android/iOS export credential-pattern scan: 98 files, zero matches. Dependency reachability separately reviewed. |

## Automated checks
- Runtime: Windows, Node 24.11.1, npm 11.6.2. Expo resolved 58.0.21, Router 58.0.25, React 19.3.0, React Native 0.88.1. SDK-aware install selected the RN patch; no peer-dependency bypass.
- Implementer ran fresh npm ci (1,150 packages), lint, typecheck, 14 initial tests, SDK compatibility check and Expo Doctor (20/20). Lead added a failing style regression and reran lint/typecheck/all tests after its fix: **15/15 pass, two suites**.
- Final `npm run export:web`, `export:android`, `export:ios`: PASS. Web JavaScript and native Hermes exports were regenerated after the style fix. Native exports are compilation evidence, not installed standalone application builds.
- `npx expo install --check`: up to date. Expo Doctor: 20/20. Package/config changes were complete before these checks; the subsequent fix touched component state/style and tests only.
- `browser-verification.py`: **6/6 pass** using isolated Chromium and the final production web export. Covers all seven direct URLs and preview disclosures; forward flow; exactly three tabs and selected state; backward links from direct entry; actual browser back; keyboard Tab/Enter and visible custom focus; all seven layouts at 320px; doubled CSS layout scale. No page JavaScript errors or external application HTTP requests observed.
- CSS zoom 200% is recorded as CSS scale, not native browser-chrome zoom. Actual screen-reader announcements and increased native font-size behavior have not been certified.
- Workflow YAML parsed with installed js-yaml: ten steps; read-only token permissions. Local evidence was recorded before PR creation; consult the PR checks for hosted execution.

## Android runtime
- PASS: SDK-matched Expo Go 58.0.5 installed and launched the same source tree in an isolated Android36 x86_64 AVD named cst17_verification (Pixel7 profile, emulator-5556).
- `android-verification.py`: one full-flow test passes, **11 screen checkpoints** covering all seven screens, Welcome → Library → Preparation → Session → Report, hardware Back through Session/Preparation/Library, then Score history/Account/Library tab actions.
- Repeated the full flow after a cold emulator restart with SwiftShader software rendering: PASS (42.96s), after restoring the test-only adb reverse and cold-starting Expo Go. Captured all seven native screens. Final Welcome shows the corrected blue 48dp link target; native XML and actual actions verify the flow. This is native runtime evidence in Expo Go, not a standalone APK, release signing or distribution test.

## Screenshots and visual review
- [Web Library](screenshots/web-library.png), [320px Library](screenshots/web-narrow-library.png), [keyboard focus](screenshots/web-keyboard-focus.png), [200% CSS scale](screenshots/web-report-css-zoom-200.png).
- All seven web destinations captured at wide and 320px widths under screenshots/. Lead inspected wide/narrow Library, focus and scaled Report captures; readable labels, preview disclosures, selected-tab underline and focus ring confirmed. Remaining captures retained for review.
- [Android Welcome](screenshots/android-welcome.png), [Android Library](screenshots/android-library.png), [Android Report](screenshots/android-report.png), [Android Score history](screenshots/android-score-history.png). All seven native captures retained. The Lead reviewed these four, including corrected link backgrounds and tab selection.

## Dependency audit and limits
`npm audit --json`: **16 affected package entries (13 low, 3 high), two underlying advisories**, not sixteen unique vulnerabilities. No supported SDK58 patch removes both at review time. Independent contextual review found no demonstrated high exploit path for this shell; residual findings and exact boundaries are in [threat-model.md](threat-model.md), tracked by #61. This is not a clean-audit claim or a general release waiver.

## Reproduce
From apps/student: `npm ci`, `npm run lint`, `npm run typecheck`, `npm test`, `npx expo install --check`, and the three export scripts. From repository root with Python Playwright/Chromium installed: `python specs/017-cross-platform-scaffold/browser-verification.py`.

Android: start the isolated AVD named cst17_verification on port5556, set ANDROID_HOME, run the SDK-matched Expo Go app through `npm run android -- --localhost --port 8087`, then run `android-verification.py`. The harness refuses other AVD names. It uses the test client's developer-menu dismissal only; no wipe or uninstall.

Mac/iOS: follow apps/student/README.md, run the same install/check commands, open an iOS simulator, run `npm run ios` (or `npx expo run:ios` for a local debug build), exercise the seven destinations, record Xcode/simulator/OS versions and actual captures. Only then verify AC1's remaining platform portion.

## Recovered failures
- Initial test-first run: five navigation failures before route files existed; corrected by implementation.
- Existing Pixel_7 AVD could not install Expo Go due to insufficient device storage. Created a separate cst17_verification AVD using the existing Android36 image; preserved old device data.
- First final browser runs used duplicate inactive-stack text selectors; scoped checks to the active page heading. The same runs and native screenshot found a real missing-link-background/focus defect; a failing-then-passing route test proves its fix.
- Initial Android recheck encountered Expo Go home/developer-menu state; harness records/dismisses that client state before checking application screens. A supplementary emulator restart initially lost its loopback forwarding and Expo Go retained a failed remote-update screen; the harness now restores only port8087 and cold-starts the test client. Final cold-start flow passes.
- Personal Edge automation denied and browser connector host unavailable. Isolated app browser tests provided local evidence without personal profiles. Independent QA stopped at a usage limit; Lead completed the recorded checks after Sandy's explicit continuation.
- First hosted Linux run 41125043406 failed at npm ci before tests: npm11.19.1 required optional @emnapi/core1.11.3 and @emnapi/runtime1.11.3 missing from the npm11.6.2 Windows lockfile. Regenerated the existing lock metadata with CI's npm11.19.1 in an isolated directory; added exactly those two package nodes, removed none, and changed no existing package versions. Clean Windows install with npm11.19.1 (scripts disabled for this metadata verification), lint/typecheck and tests were rerun; ordinary script-enabled Linux installation and all checks are enforced by the replacement hosted run. Consult the PR checks for its result.
