# Case-Study-Tech

An application for students to practice counseling with simulated clients and receive formative feedback.

The student app lives in `apps/student` (Expo/React Native for web, Android, and iOS). The accounts service lives in `services/accounts` (Python/FastAPI). Grading, scenarios, and final Figma fidelity remain in their separate issues.

## Student application

The [shared React Native / Expo project](apps/student/README.md) combines the navigation preview from #17 with Google-only sign-in, sign-out, and account deletion requests. Library, Preparation, Session, Report, and Score history are protected preview screens. Counseling sessions and scores are not implemented yet.

```sh
cd apps/student
npm ci
npm run lint
npm run typecheck
npm test
npm run export:web
npm run web
```

See the app README for native startup and export commands, tool requirements, and configuration boundaries. iOS simulator startup requires macOS and Xcode. Build/export success alone does not establish an installed native app works.

## Accounts service and rules

```powershell
cd services/accounts
uv sync --python 3.12
uv run --python 3.12 python -m pytest -q
uv run --python 3.12 ruff check cst_accounts tests
uv run --python 3.12 mypy cst_accounts
```

From the repository root, with Java 21+ and Firebase CLI available:

```powershell
npm ci --prefix infra
firebase emulators:exec --only firestore --project demo-casestudy-tech "npm --prefix infra test"
```

The `demo-` project ensures rules tests do not use live Firestore. Each npm directory owns its own lockfile; run installs sequentially for a given directory. Authentication needs the configuration described in [the account runbook](docs/accounts-setup.md); there is no production mock-sign-in path.

## Current boundaries

Account presentation is a functional foundation, not completion of the Figma fidelity deliverable #56/#58. Library and Score history are protected previews, not completed #28/#41 features. The private accounts service, gateway, tested Firestore rules, hourly deletion worker and cleanup alert policies are deployed in the development project. Live access/CORS and synthetic owner-only cleanup checks passed; the final full Terraform plan has no changes. Real Google sign-in on web and Android still gates #25; iOS proof moved to #103. See [the work log](docs/implementation/issue-4.md), [deployment runbook](infra/accounts/README.md), and [Mac handoff](docs/ios-mac-handoff.md).

## Feature evidence

- [Issue #17 specification](specs/017-cross-platform-scaffold/spec.md)
- [Architecture and integration notes](specs/017-cross-platform-scaffold/plan.md)
- [Verification](specs/017-cross-platform-scaffold/verification.md)
- [Review](specs/017-cross-platform-scaffold/review.md)
- [Access and accounts specification](specs/004-access-accounts/spec.md)
