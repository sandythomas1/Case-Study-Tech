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
