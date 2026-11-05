# CaseStudy Tech

Student counseling simulation application. The initial access/account slice lives in `apps/student` (Expo/React Native, web/iOS/Android) and `services/accounts` (Python/FastAPI). Grading, scenarios, and final Figma fidelity remain in their separate issues.

## Local verification

```powershell
cd services/accounts
uv sync --python 3.12
uv run --python 3.12 python -m pytest -q
uv run --python 3.12 ruff check cst_accounts tests
uv run --python 3.12 mypy cst_accounts

cd ../../apps/student
npm ci
npm run typecheck
npm run lint
npm test
npx expo export --platform web
```

From the repository root, with Java 21+ and Firebase CLI available:

```powershell
npm ci --prefix infra
firebase emulators:exec --only firestore --project demo-casestudy-tech "npm --prefix infra test"
```

The `demo-` project ensures rules tests do not use live Firestore. Each npm directory owns its own lockfile; run installs sequentially for a given directory. Start the client with `npm start` in `apps/student`. Authentication needs the configuration described in [the account runbook](docs/accounts-setup.md); there is no production mock-sign-in path.

## Current boundaries

Account presentation is a functional foundation, not completion of the Figma fidelity deliverable #56/#58. Library/history are protected placeholders, not completed #28/#41 features. The private accounts service, gateway, tested Firestore rules, hourly deletion worker and cleanup alert policies are deployed in the development project. Live access/CORS and synthetic owner-only cleanup checks passed; the final full Terraform plan has no changes. Google OAuth/native sign-in, user-owned Mac iOS installation, student dependency findings and remaining UI integration still gate #4. See [the work log](docs/implementation/issue-4.md), [deployment runbook](infra/accounts/README.md), and [Mac handoff](docs/ios-mac-handoff.md).
