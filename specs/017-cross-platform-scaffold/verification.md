# Verification — issue #17 scaffold

Date: 2026-10-30. Worktree C:/cst17, branch feature/17-cross-platform-scaffold, base dev aa6ea60.

## Acceptance criteria

| Criterion | Result | Evidence |
| --- | --- | --- |
| AC1: web, Android emulator, iOS simulator start from the same project and show the shell | PASS (iOS added 2026-11-22) | Actual web navigation verified. Android result below. The iOS simulator was verified on 2026-11-22 under #103; see "iOS runtime" at the end. |
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

Mac/iOS: see "Reproduce on iOS" in the "iOS runtime" section at the end.

## Recovered failures
- Initial test-first run: five navigation failures before route files existed; corrected by implementation.
- Existing Pixel_7 AVD could not install Expo Go due to insufficient device storage. Created a separate cst17_verification AVD using the existing Android36 image; preserved old device data.
- First final browser runs used duplicate inactive-stack text selectors; scoped checks to the active page heading. The same runs and native screenshot found a real missing-link-background/focus defect; a failing-then-passing route test proves its fix.
- Initial Android recheck encountered Expo Go home/developer-menu state; harness records/dismisses that client state before checking application screens. A supplementary emulator restart initially lost its loopback forwarding and Expo Go retained a failed remote-update screen; the harness now restores only port8087 and cold-starts the test client. Final cold-start flow passes.
- Personal Edge automation denied and browser connector host unavailable. Isolated app browser tests provided local evidence without personal profiles. Independent QA stopped at a usage limit; Lead completed the recorded checks after Sandy's explicit continuation.
- First hosted Linux run 41125043406 failed at npm ci before tests: npm11.19.1 required optional @emnapi/core1.11.3 and @emnapi/runtime1.11.3 missing from the npm11.6.2 Windows lockfile. Regenerated the existing lock metadata with CI's npm11.19.1 in an isolated directory; added exactly those two package nodes, removed none, and changed no existing package versions. Clean Windows install with npm11.19.1 (scripts disabled for this metadata verification), lint/typecheck and tests were rerun; ordinary script-enabled Linux installation and all checks are enforced by the replacement hosted run. Consult the PR checks for its result.

## Re-verification 2026-11-19 (Expo 58.0.26, commit 4cd1407)

Why this rerun: e4ddd04 bumped Expo 58.0.21 to 58.0.26 and updated eslint within range (about 970 lockfile lines, no app source changes), and 4cd1407 repaired the lockfile. The runtime evidence above was recorded at ed8a6a2. Worktree C:/cst17, HEAD 4cd1407; only the uncommitted build-log.md entry from the Lead was present. Resolved locally: Expo 58.0.26, expo-router 58.0.32, React Native 0.88.1. QA ran under Node 24.11.1, npm 11.6.2 (QA ran no install).

Lead, with npm 11.19.1 (not repeated by QA): clean `npm ci`, lint, typecheck, Jest 15/15, `npx expo install --check`, and web/android/ios exports all PASS.

QA re-ran the following:

| AC | Test(s) / screenshot that prove it | Command | Result | Evidence |
| --- | --- | --- | --- | --- |
| AC1, web | `browser-verification.py`, 6 tests: all seven direct URLs and preview disclosures, forward flow, exactly three tabs and selected state, backward links from direct entry, browser Back, keyboard Tab/Enter and focus ring, seven layouts at 320px, 2x CSS scale. No page JS errors or external requests. | From apps/student, `npm run export:web` (fresh, 15:38 local). Then from the repo root, `python specs/017-cross-platform-scaffold/browser-verification.py` (Playwright 1.58.0, bundled Chromium, fresh ephemeral profile, no personal profile). | PASS, 6/6 in 27.2s | All 16 `web-*.png` were overwritten by the run and are **byte-identical** to the committed ed8a6a2 captures (git shows no diff), so web rendering did not change under the bump. QA opened [web-library](screenshots/web-library.png), [web-narrow-library](screenshots/web-narrow-library.png), [web-keyboard-focus](screenshots/web-keyboard-focus.png) and [web-report-css-zoom-200](screenshots/web-report-css-zoom-200.png): readable labels, preview disclosure, selected-tab highlight and focus ring are present. |
| AC1, Android | `android-verification.py`: one full-flow test, 11 screen checkpoints covering all seven screens: Welcome → Library → Preparation → Session → Report, hardware Back ×3, then Score history/Account/Library tabs | Cold boot of the isolated `cst17_verification` AVD on emulator-5556 (`-no-snapshot-save -gpu swiftshader_indirect`). Then `npm run android -- --localhost --port 8087` with ANDROID_HOME set, then `python specs/017-cross-platform-scaffold/android-verification.py`. The harness restores adb reverse 8087 and cold-starts Expo Go. | PASS, 11/11 checkpoints in 62.0s, first attempt | Expo Go 58.0.5 (SDK 58 match) was already installed; nothing was installed, wiped or uninstalled. Metro bundled 1290 modules with no errors or warnings in its log. All seven `android-*.png` were recaptured. QA opened [android-welcome](screenshots/android-welcome.png) (blue 48dp link, readable white label) and [android-score-history](screenshots/android-score-history.png) (selected-tab highlight). Afterwards QA removed the adb reverse and stopped Metro, the emulator and the adb server. |
| AC1, iOS simulator | none | none | NOT VERIFIED (on 2026-11-19) | There is no Mac or Xcode on this machine. The iOS export the Lead re-ran is compilation evidence only and is not counted as simulator evidence. Verified later under #103; see "iOS runtime" below. |
| AC2 | Lead's clean-install suite | Lead: `npm ci`, `npm run lint`, `npm run typecheck`, `npm test` (npm 11.19.1) | PASS (Lead-reported, not repeated by QA) | Jest 15/15. Hosted CI is the authority for script-enabled Linux `npm ci`; consult the PR #71 checks. |
| AC3 | Bounded credential-pattern scan of tracked source/config (`src`, app.json, package.json, tsconfig, babel/eslint config) plus every file in fresh `dist/web` and the Lead's `dist/android` and `dist/ios` | grep -E for AWS AKIA, Google AIza, PEM private keys, GitHub ghp_/github_pat_, Anthropic sk-ant-, OpenAI sk-, Slack xox, JWTs, service-account JSON, client_secret, and quoted api_key/secret/password/token assignments | PASS, bounded | 101 files scanned, 0 matches, 0 read errors. The original ed8a6a2 regex was not recorded, so this is an equivalent common-format scan, not a byte-for-byte repeat. There was no source change, so the static app.json and source review stand. |

Regressions: none observed. Overall: AC1 PARTIAL (web PASS, Android PASS, iOS not verified), AC2 PASS, AC3 PASS (bounded).

## iOS runtime 2026-11-22 (#103, base dev 90efd25)

Why this run: #17 had no Mac, so the iOS part of AC1 was never verified. #25 has since put every
screen except Welcome and Sign in behind Google sign-in, so the shell now has eight screens, and
reaching them on iOS needs real native sign-in. Expo Go can't do that, so this run uses a local
debug build (`npx expo run:ios`) with expo-dev-client, loading the same source tree from Metro.

Environment:

| Item | Value |
| --- | --- |
| Device | iPhone 17 Pro simulator, iOS 26.2 |
| Xcode | 26.2 (17C52), Swift 6.2.3 |
| Host | macOS 15.6, Apple silicon (arm64) |
| SDK | Expo 58.0.26, React Native 0.88.1, expo-router Stack.Protected |
| Sign-in | @react-native-google-signin/google-signin 16.2.0 (GoogleSignIn 9.2.0, AppAuth 2.1.0) |
| Tooling | Node 24.22.3, npm 11.19.1, CocoaPods 1.16.2, Maestro 2.12.1 |
| Google account | A test account on the dev OAuth app's test-user list. Its address is not recorded anywhere in the repo. |

| AC (#103) | Test(s) / screenshot that prove it | Command | Result | Evidence |
| --- | --- | --- | --- | --- |
| The iOS simulator starts the shell from the same project, and all eight screens are reachable | `ios-verification.yaml` visits Welcome, Sign in, Library, Preparation, Session, Report, Score history and Account, and asserts each one's body text | `maestro --device <udid> test specs/017-cross-platform-scaffold/ios-verification.yaml` | PASS, one run, 3m 10s, exit 0 | [ios-welcome](screenshots/ios-welcome.png), [ios-sign-in](screenshots/ios-sign-in.png), [ios-library](screenshots/ios-library.png), [ios-preparation](screenshots/ios-preparation.png), [ios-session](screenshots/ios-session.png), [ios-report](screenshots/ios-report.png), [ios-score-history](screenshots/ios-score-history.png), [ios-account](screenshots/ios-account.png). All eight were opened and checked: each renders its title, preview disclosure and links. |
| Tabs show their selected state, and backward links return to the expected screen | The same flow: Back to Session, Back to Preparation, Back to Library and Return to Library each land on the expected body text. Library, Score history and Account taps assert `selected: true` on the new tab and not on the old one | Same run | PASS | The selected-tab highlight is visible in ios-library, ios-score-history and ios-account. |
| Google sign-in and sign-out work: a valid sign-in opens Library, and after sign-out the protected screens are unreachable | The same flow: a signed-out `casestudytech://library` link lands on Sign in. Native Google sign-in lands on Library. After Sign out, links to library, library/report, history and account all show Sign in with no protected body text. A cold restart (stop, launch) stays signed out | Same run | PASS | ios-sign-in shows the signed-out guard. ios-library is the screen after sign-in. ios-account shows no email address. Recording: see the PR (the Google pages are cut out). |
| Screenshots and environment details are recorded here | This section | none | PASS | The environment table above and the eight `ios-*.png` captures. |

How the sign-in was done: Google doesn't keep its web session between sign-ins on this simulator,
so the tester typed the test account's sign-in by hand when the flow reached Google's page. The
flow waits up to 5 minutes for that. Google asked for a passkey, which the simulator can't provide,
so the tester chose "Try another way" and used the password. The flow taps an account in Google's
chooser if one appears, but the chooser never appeared in this run. Everything else in the run is
automated.

Local build patch (not committed): expo-modules-jsi 58.0.23 doesn't compile on Xcode 26.2 /
Swift 6.2.3 ("sending 'slot' risks causing data races"), which is upstream expo/expo#52754. For this
run only, `node_modules/expo-modules-jsi/apple/Sources/ExpoModulesJSI/Runtime/Values/JavaScriptObject.swift`
was patched to pass the slot pointer into `JavaScriptActor.assumeIsolated` as a `UInt(bitPattern:)`
and rebuild it inside the closure. The patch doesn't change behavior. No app source, package.json or
lockfile change was needed, and no iOS-only app defect turned up. Anyone building on Xcode 26.x
needs the same workaround until Expo ships a fix.

Recovered failures:

- The first build failed on the expo-modules-jsi error above. The local patch fixed it.
- The dev launcher showed "Searching for development servers". The flow now opens the exact
  `exp+case-study-tech-student://?__expo_url=...` link that `expo run:ios` uses.
- iOS asked "Open in Case-Study-Tech?" on deep links. Every openLink is now followed by an optional
  tap on Open.
- An earlier draft of the flow used Maestro's `clearKeychain`, which wipes the whole simulator
  keychain, including Google's session. It was removed. `launchApp clearState` resets the app.
- One run timed out at Google's passkey challenge. The wait was raised to 5 minutes, and the
  "Try another way" step is now documented.

### Reproduce on iOS

1. On a Mac with Xcode 26.x and an iOS 26.x simulator, follow apps/student/README.md and
   [the Mac handoff](../../docs/ios-mac-handoff.md): Node 24, `npm ci`, and an ignored env file
   with the public API address and the web and iOS OAuth client IDs. Apply the #52754 workaround
   above if expo-modules-jsi still fails to compile.
2. From apps/student, run `npx expo run:ios --device "<simulator name>"`, then revert the
   `package.json` script rewrite that prebuild makes (`git checkout -- apps/student/package.json`).
3. Keep Metro running on port 8081, then from the repo root run
   `maestro --device <simulator-udid> test specs/017-cross-platform-scaffold/ios-verification.yaml`
   and sign the test account in by hand when Google's page appears. The flow's header explains the
   options.

Overall after #103: AC1 PASS (web PASS, Android PASS, iOS PASS), AC2 PASS, AC3 PASS (bounded).
