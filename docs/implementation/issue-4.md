# Access and accounts work log

Branch: `feature/4-access-accounts`, based on `origin/dev` at `aa6ea60`. Worktree: `C:/Users/sandy/Desktop/dev/Case-Study-Tech-issue4`. The original working tree's draft documents are preserved. No commit, push, PR, or application deployment is implied by local implementation.

## 2026-10-21 initial scope

Started #4 with prerequisites #17/#18 and account stories #25/#26/#46/#50 tracked In Progress. User requested continuous shared-memory/lesson appends and authorized a new Firebase/Google Cloud project. Reference/scoring work remains in its own workstreams.

## Checkpoint 1

Created `casestudy-tech-dev-2e03d0`, Firebase registration and free-tier Firestore Native in `us-central1`. Added a provider-neutral API, owner authorization, and deletion workflow. TDD produced 16 expected failures against the empty router, then 16 passes. An initial pytest collection error was corrected by using `python -m pytest` and a project-local pytest configuration.

## Checkpoint 2

Production Identity Platform and Firestore adapters added. Eight SDK-boundary tests bring backend total to 24 passes. Backend Ruff and mypy checks pass. Nine client session tests pass after seven expected stub failures, covering confirmation, refresh, malformed credentials and sign-out races. Functional account UI and platform Google/SecureStore adapters added. No live OAuth success is claimed.

Identity Platform setup is blocked on billing (`BILLING_NOT_ENABLED`); the owner's billing choice is pending. The first API attempt also needed a quota-project header. Client dependencies report 16 high-severity transitive audit findings in Expo/Metro tooling (`braces`, `node-forge` dependency chains); nonbreaking audit repair did not clear them, and the proposed forced downgrade is inappropriate. Treat these as unresolved release checks, not a clean audit.

One rules-test run failed because its dependencies were not installed. An overlapping dependency install was stopped; installs are now sequential and the rules-test dependencies are being restored with `npm ci`. Latest Firebase test packages required Node >=24.12, so the test harness uses the compatible Firebase 12/rules-testing 5 line with a lockfile. These are tooling failures, not passing rules evidence.

## Completion evidence still required

- Firestore emulator rules tests, production-store integration and cross-owner deletion proof.
- Client lint/typecheck and platform bundle results after final changes.
- Real Google-only provider/OAuth configuration and browser/native sign-in.
- Private deployed gateway/service, configured Secret Manager/IAM, reviewed deployed rules and a scheduled/monitored deletion sweep.
- Internal iOS installation, native device checks, and the separate Figma/accessibility deliverables.
- Dependency audit remediation or an explicit evidence-backed release decision.

No acceptance checkbox should be inferred complete from a mocked flow or an unexecuted deployment template.

## Checkpoint 3 and verification handoff

| Check | Result |
| --- | --- |
| Account HTTP/domain/SDK-boundary tests | 26 passed |
| Client session lifecycle tests | 12 passed |
| Direct Firestore security rules | 4 passed in the demo emulator |
| Real Firestore store and HTTP integration | 5 passed in the demo emulator |
| Python Ruff and mypy | Passed; seven production modules checked |
| Student TypeScript strict and ESLint | Passed |
| Expo Doctor | 20 of 20 checks passed |
| Web, Android Hermes and iOS Hermes exports | Passed with protected Expo Router routes |
| Backend dependency audit | No known vulnerabilities |
| Infrastructure test dependency audit | 0 vulnerabilities after grpc-js 1.14.6 override |
| Student toolchain audit | 20 high affected entries remain; tracked in #61 |
| Targeted API/private-key scan | No matches in new source/configuration |
| Browser rendered smoke check | Not run: browser automation inventory is empty |
| Live OAuth/gateway/deletion schedule and native installation | Not verified; configuration/authorization/device prerequisites remain |

Tests exposed and fixed deletion retry fairness (failed owners move to a later attempt without changing their original deadline) and a late-deletion-response race that could otherwise sign out a newer client session. Regression tests failed before each fix and passed afterward. Deletion errors now remain visible inside the confirmation modal; its accepted result survives navigation back to Welcome.

Resolved the emulator harness audit with a supported same-major grpc override; reran its rules tests after updating the lockfile. The current registry versions of braces and node-forge still fall inside the reported affected ranges, so no unsupported forced downgrade is applied to the student app. #61 tracks remaining remediation under the platform epic.

Recorded local acceptance evidence only: #26's cross-student API/direct-database test, #46's explicit confirmation, and #50's distribution constraint documentation. Remaining criteria and all issue completion states remain open. This is local work in an uncommitted feature worktree; it has not landed in dev.

The pending billing-link question has no affirmative answer recorded. New project and Firestore exist, but Identity Platform initialization still requires billing. Google provider/client registration, service/gateway deployment, monitored cleanup and internal iOS installation are still needed before epic #4 is complete. Original draft documents remain untouched.

## Checkpoint 4: authorized source handoff

The user authorized committing and pushing this feature branch on 2026-10-21. The handoff includes the account implementation, configuration templates, regression tests and setup documentation above. Generated dependencies, build outputs, local credentials and scaffold-specific tool preferences are excluded. Verification remains the 47 passing tests and checks recorded at checkpoint 3; no application behavior changed during this handoff.

The branch is intended for remote review preparation only. No pull request, protected-branch merge or application deployment is authorized by this handoff. All related issues remain In Progress, including the unresolved student dependency findings in #61. The resulting commit and push evidence will be recorded in the GitHub issues and shared memory.

## Checkpoint 5: paid upgrade authorized, blocked by Google quota

The user authorized the paid upgrade and another commit/push if needed. Attempted to link `casestudy-tech-dev-2e03d0` to the existing open Firebase Payment billing account. Google rejected the link with `FAILED_PRECONDITION`, `QuotaFailure`, and `Cloud billing quota exceeded`, pointing to its billing project quota request form. Read-only checks found one open billing account and five already linked projects. These facts do not identify the exact quota or authorize changing existing projects.

Verified that the target project's billing remains disabled. Retried Identity Platform initialization with the project quota header and received HTTP 400, `BILLING_NOT_ENABLED`. No live authentication success, paid upgrade, support submission, application deployment or issue completion is claimed. Added a support request draft and precise retry/readback steps to `docs/accounts-setup.md`, without account IDs, contact information or credentials.

This checkpoint changes documentation only. The 47 previously passing tests are not rerun because application code and configuration are unchanged. Issue #4 remains In Progress: billing is externally blocked, and its live OAuth, gateway, deletion scheduling and native installation acceptance evidence is still outstanding. Existing project billing and original draft documents remain untouched.

## Checkpoint 6: authorized billing replacement and Identity Platform initialization

The owner explicitly authorized removing Auto-Cloud-Deploy from Firebase Payment and replacing it with CaseStudy Tech. Verified the source account association, unlinked `auto-cloud-deploy-500705`, then linked `casestudy-tech-dev-2e03d0` to the existing billing account. Live readback confirms Auto-Cloud-Deploy billing is disabled and CaseStudy Tech billing is enabled. The source project itself was not deleted. Account membership now includes CaseStudy Tech and excludes Auto-Cloud-Deploy, with the other four associations preserved.

Identity Platform initialization then succeeded with HTTP 200. Configuration readback returned `projects/613104664964/config`, with anonymous, email and phone sign-in disabled. The billing and initialization blocker is resolved; actual Google OAuth client/provider registration and successful student sign-in are not yet verified.

Updated the setup document to reflect current paid billing and remove the obsolete quota-request instructions. Repository changes are documentation only; no application tests were rerun, and the previously recorded 47 passing tests remain local evidence. Issue #4 remains In Progress pending its live OAuth, gateway/service, scheduled deletion and native installation checks. No application deployment, PR or merge was performed.

## Checkpoint 7: deployed account boundary and installed Android verification (2026-10-22)

Completed the development account infrastructure: private Cloud Run accounts service, authenticated API Gateway, separate deletion job/service identity, hourly UTC scheduler, restricted Identity API key in Secret Manager, scoped IAM, tested Firestore rules and two cleanup alert policies. The successful Cloud Build is `e7a36ab1-224c-4d81-8a9b-4e548e89072b`; deployments pin its verified image digest. Gateway health/auth/CORS checks passed (six), private-service IAM and independent student-token rejection passed (four), actual synthetic account/score cleanup passed without affecting the second owner, and the actual scheduler dispatched a successful execution. The final full Terraform plan reports no changes. No student bundle or session/grading service was deployed.

Recovered the first Cloud Build's missing bucket-metadata permission with bucket-scoped access, and a later logging failure by using Cloud Logging rather than mutable GCS log objects. Alert creation initially returned metric-not-found while new log metrics propagated; the subsequent full apply created both policies. Operational notification destinations and public-auth abuse controls remain required before enrolling students.

Rendered web tests exposed a blank-page regression on protected deep links (initially one pass, five failures). Added an explicit `/sign-in` route and SDK 58 protected-route redirect targets. All seven anonymous browser routes now show Welcome. Final verification totals 58 automated tests: backend 30, client 12, database/emulator nine and rendered web seven. Ruff, mypy, strict TypeScript, ESLint and web/iOS/Android Hermes exports pass. A fresh isolated source install also passed lint/typecheck and all 12 client tests. Targeted credential checks passed across 68 final exported files.

Android native compilation, installation and launch succeeded after resolving Windows native path constraints with a short source copy (`C:/c4`), verified official Ninja 1.13.2 and the optional checked-in Gradle init script setting the object-path maximum to 240. The successful CMake cache confirms those values. The Android 36 emulator passed six anonymous UI checks: Welcome plus history/account/preparation/session/report deep links. The local APK uses template debug signing and is not a student release. Earlier long-path attempts, installation before emulator boot, and a System UI timeout were failures before the final successful checks; shared SDK/registry settings were preserved.

Sandy explicitly owns all Apple development on Mac. Added `docs/ios-mac-handoff.md` with the actual Firebase/bundle identifiers, deployed API URL, public OAuth configuration and installed core-flow checklist. Google-only provider/client registration and real sign-in/sign-out/refresh/deletion UI evidence remain outstanding: no connected authenticated browser is available here, and actual client IDs were not supplied. #61 still reports 20 high affected dependency entries across two upstream advisories; no forced downgrade or release-risk acceptance was applied. #18 still requires its separate session/grading services. #4 and its dependent incomplete stories remain open; compilation or Mac ownership does not satisfy installed iOS acceptance.

See [the final integration evidence](issue-4-live-verification.md), [infrastructure runbook](../../infra/accounts/README.md) and [dependency audit](../student-toolchain-audit.md). This checkpoint is being committed/pushed under the user's existing authorization. Feature review is separate from protected-branch merges and release. Original workspace draft documents remain untouched. Commit/PR links and exact board transitions are recorded in the issue progress comments and shared memory.