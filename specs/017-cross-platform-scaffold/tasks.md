# Tasks: Cross-platform student application scaffold

> **Phase:** Tasks Â· **Status:** implementation done; acceptance pending Mac evidence Â· **Date:** 2026-10-30
> Derived from `plan.md`; production work stays in `apps/student`. Preserve concurrent specification edits and the read-only account worktree.

## Legend
- `[ ]` todo Â· `[~]` in progress Â· `[x]` done; `(dep: N)` indicates prerequisites.
- Every task has one owner. No parallel markers: app/config/test tasks share integration boundaries.
- `plan:` identifies the sections needed in addition to Summary. Test-first tasks may initially fail until their implementation dependencies land.

## Setup
- [x] 1. Create `apps/student/package.json`, lockfile, strict `tsconfig.json`, ESLint/Jest configuration, public `app.json`, and app-local `.gitignore`; add compatible SDK 58 runtime/test packages and documented npm scripts. Done: clean dependency resolution without peer bypasses and SDK check passes. @implementer Â· plan: Stack & Dependencies, Deployment Target, Security & Privacy

## Tests
- [x] 2. Add failing real-route tests in `apps/student/tests/navigation.test.tsx` using Jest Expo/RNTL 14 and actual layouts/screens; cover forward flow, tab destinations/selection, every direct route, explicit backward links, and preview notices. Done: failures identify missing user behavior rather than mocked routing. (dep: 1) @implementer Â· plan: Architecture, API Contract, Testing Strategy

## Core Implementation
- [x] 3. Implement `src/components/PreviewScreen.tsx` and shared navigation styling under `apps/student`, with exact `ui.md` copy, heading semantics, scrolling/safe areas, wrapping, visible web focus, and usable targets. Done: all needed screen variants render without fake practice/account controls. (dep: 2) @implementer Â· plan: Architecture, UI and accessibility contract, Security & Privacy
- [x] 4. Add root Welcome and `(student)` three-tab layout plus Library child Stack and all seven route files under `apps/student/src/app/`; use absolute Router links and explicit backward destinations. Done: behavior tests pass including direct entry and Library selection in its child path. (dep: 3) @implementer Â· plan: Architecture, PR #62 integration boundary, API Contract, Testing Strategy

## Observability & Docs
- [x] 5. Write `apps/student/README.md` with npm install/check/start/export commands, platform prerequisites, SDK-matched client/debug-build fallback, Mac simulator handoff, and PR #62 reconciliation notes. Done: a fresh-clone operator can follow it without credentials, cloud services, or paid builds; iOS limits are explicit. (dep: 4) @implementer Â· plan: Deployment Target, Observability, Testing Strategy, Risks & Trade-offs

## Verification (maps 1:1 to spec Acceptance Criteria)
- [ ] 6. **AC1:** Exercise running web on all seven routes, keyboard/back/direct links, 320px and 200% zoom; launch Android emulator and iOS simulator and capture shell/path screenshots per `ui.md`. Record distinct results/evidence in `specs/017-cross-platform-scaffold/verification.md`; leave AC1 unchecked if iOS is unavailable and include the Mac handoff. (dep: 5) @qa Â· plan: API Contract, UI and accessibility contract, Testing Strategy
- [x] 7. **AC2:** From a clean `npm ci` run lint, strict typecheck, and route behavior tests; record commands, counts, outcomes, and SDK compatibility in `specs/017-cross-platform-scaffold/verification.md`. Done: all checks pass and tests exercise real screen/navigation behavior. (dep: 5) @qa Â· plan: Stack & Dependencies, Testing Strategy
- [x] 8. **AC3:** Produce all three platform exports and review `apps/student` source/config/lock plus exported bundles for credentials, account/AI integration, network/storage code, and retained content; record scope and resolved findings in `specs/017-cross-platform-scaffold/verification.md`. Done: no prohibited application behavior or credentials; export evidence is distinguished from native launch evidence. (dep: 5) @qa Â· plan: Security & Privacy, Data Model, Testing Strategy

## Final task dispositions
- Tasks1–5,7–8 verified; Lead added credential-free app-check CI and fixed/tested the real Link/asChild style regression.
- Task6 partially verified: all seven web routes, keyboard/back/320px/CSS-scale checks and actual Android ExpoGo flow/tabs/hardwareBack pass. iOS simulator and actual browser-chrome zoom/screen-reader certification remain unverified. Keep task6 open; no native binary distribution acceptance inferred.
- Runtime lock resolves Expo58.0.21/RN0.88.1 and jest-expo58.0.13. Static public app.json avoids any environment/credential configuration.
