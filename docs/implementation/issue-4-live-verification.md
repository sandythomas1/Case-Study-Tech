# Account integration evidence — 2026-10-22

Epic #4 remains In Progress. This document separates verified development behavior from the real Google/native flows that still require completion. It does not authorize a student release, close sub-issues or imply a protected-branch merge.

## Verified

| Check | Result |
| --- | --- |
| Backend HTTP/domain/provider tests | 30 passed; includes four browser-origin/preflight checks |
| Client lifecycle tests | 12 passed |
| Direct Firestore rules in demo emulator | 4 passed |
| Real Firestore store/HTTP tests in demo emulator | 5 passed |
| Rendered exported web application | 7 passed: root, sign-in, history, account, preparation, session, report show Welcome without a session |
| Backend Ruff and project-configured mypy | Passed; seven production modules checked |
| Client strict TypeScript and ESLint | Passed after the router fix, including the fresh isolated source install |
| Final web, iOS Hermes, Android Hermes exports | Passed after the router fix |
| Android native APK and installed UI | Build and install passed; Welcome and all five protected deep links showed only Welcome on the Android 36 emulator (six checks) |
| Terraform validate/format | Passed; google/google-beta 7.46.1 pinned |
| Final full Terraform plan | Exit 0, no changes after successful alert-policy retry |

The rendered test first produced one pass and five failures: protected deep links changed the URL to `/` and displayed a blank page. A distinct `/sign-in` route and explicit SDK 58 `Stack.Protected` redirects fixed the regression. Seven browser checks now pass without a token fixture, mocked sign-in or production auth bypass. The resulting Welcome screenshot was visually inspected. Reproduce with a fresh web export, `uvx --from playwright==1.64.1 playwright install chromium`, then `uv run --no-project --python 3.12 --with playwright==1.64.1 --with pytest==9.1.1 python -m pytest infra/accounts/test_web_routes.py -q`.

The final Android build used a fresh short app source copy at `C:/c4`, Android Studio's JDK, verified Ninja 1.13.2 and the checked-in optional Gradle init script with `CMAKE_OBJECT_PATH_MAX=240`. The actual successful variant's CMake cache confirmed both settings. `assembleRelease` succeeded (881 tasks), producing a 30,121,468-byte x86_64 APK. Installation and launch succeeded on the task's Pixel_7 Android 36 emulator. Native UI hierarchy checks passed for Welcome, history, account, preparation, session and report; a final screenshot was visually inspected. The app uses the template debug signing identity and has no configured Google OAuth client. This local artifact is not an internal student release or evidence of successful Google sign-in. Earlier long-path build attempts, an install before emulator boot, and an emulator System UI timeout failed before the final successful checks. No shared SDK or Windows registry setting was changed.

These results total 58 automated assertions/tests (30 backend, 12 client, nine database/emulator and seven rendered web tests), plus six installed Android route checks and the separate live cloud probes. A targeted credential-pattern scan of all 68 final exported files found no API-key, private-key or GitHub-token matches; only public settings are configured in the client. This scan supplements source/configuration review and does not replace the dependency audit.

## Live cloud proof

- Cloud Build `e7a36ab1-224c-4d81-8a9b-4e548e89072b` succeeded. Deployment pins image digest `sha256:8c6e9150426a4ee7af19542c75d1e00547d4e80d004c17f16dd7f6500105411c`.
- Gateway `https://accounts-7tnmor5w.uc.gateway.dev`: GET health 200; missing student credentials on current-student and deletion routes 401; forged score-route credential 401; allowed-origin OPTIONS 200 with the exact allow-origin; untrusted-origin OPTIONS 400 without permission. Six checks passed. Early provisioning probes returned 404 and were not counted as passing.
- Private service `https://accounts-447ob3nwoa-uc.a.run.app`: unauthenticated health 403, operator-authenticated health 200. Independent backend checks reject operator/non-student and forged forwarded credentials with 401. The gateway alone does not establish student identity at the backend.
- Deployed Firestore rules compiled/released successfully after four emulator security tests passed. Runtime project IAM was reviewed: account and deletion service identities hold their custom roles, build identity holds logging access, and gateway/scheduler service agents hold their designated service-agent roles. Service/job/secret/artifact access is scoped in Terraform; no downloaded service-account key, broad runtime Owner/Editor or public Run invoker binding is added.
- Actual deletion execution `account-deletion-62z4g`: completed 1, failed 0, overdue 0. The opt-in live probe verified account and scores removed before the original deadline, completed denial marker retained, another synthetic owner's score preserved. It then cleaned its synthetic fixtures. These accounts had no emails or session content and did not exercise Google sign-in.
- Cloud Scheduler's hourly UTC job dispatched `account-deletion-glms6`, which completed successfully. Two cleanup alert policies now exist. Their first creation attempts returned metric-not-found during Google's propagation period; a subsequent full plan/apply created both policies, and the final full plan has no changes. Incident notification destinations still need operational configuration before student use.

The current module deploys account infrastructure only. #18 also owns the separate session and grading services, which are not implemented by these account resources.

## Closure gates still open

- #25: actual Google OAuth web/iOS/Android clients and Google-only provider configuration, then real sign-in/sign-out/refresh and log checks. No connected Google console browser is available in this session; no public client IDs were supplied. The exported app intentionally shows the unavailable sign-in state until configured.
- #26: gateway rejection, owner-isolation tests, seven rendered web route checks and six installed Android route checks are verified. Review and the positive real-Google journey with #25 remain; Apple native verification belongs to the Mac handoff.
- #46: confirmation and scheduled actual cleanup are verified. Confirmed deletion, immediate sign-out and denied old-session reads through the actual signed-in student UI remain to demonstrate.
- #50: Sandy owns all Apple development on Mac. An installed internal/TestFlight core-flow demonstration is still required; [the Mac handoff](../ios-mac-handoff.md) provides identifiers, public configuration and verification steps. Bundle export alone does not meet it.
- #17: clean-source lint/typecheck and 12 unit tests pass, exported bundle credential checks pass, and Android compilation/install plus six anonymous UI checks pass. The Mac iOS simulator build and authenticated navigation-shell demonstration remain independent of Hermes/web export.
- #61: clean-install audit still reports 20 high affected dependency entries across two advisories. Registry latest versions are still affected. See [the dependency evidence](../student-toolchain-audit.md); no forced Expo downgrade or release-risk acceptance was applied.

Original workspace draft documents were preserved. Current delivery is a feature branch; merge/release status must follow the actual PR/promotion results.
