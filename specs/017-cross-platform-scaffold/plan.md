# Plan: Cross-platform student application scaffold

> **Phase:** Plan · **Status:** validated · **Date:** 2026-10-30
> Derived from the clarified `spec.md`; navigation and copy incorporate `ui.md`.

## Summary
Create one standalone Expo SDK 58 application under `apps/student`, using Expo Router and strict TypeScript. Seven local preview screens share a small accessible frame. Library owns the nested practice navigation; Library, Score history, and Account are the only tabs. No authentication, data entry, persistence, service integration, or cloud setup is introduced. Preserve the account branch's `src/app` and `(student)` integration seam without importing its account behavior.

## Architecture
- `apps/student/package.json` uses `main: expo-router/entry`; there is no competing `App.tsx` entry or root workspace to maintain.
- `src/app/_layout.tsx` owns the root Stack and safe-area setup. `src/app/index.tsx` is Welcome; `(student)/_layout.tsx` owns the three JavaScript Tabs from `expo-router`.
- `(student)/library/_layout.tsx` owns a Stack containing `index.tsx`, `preparation.tsx`, `session.tsx`, and `report.tsx`. All four retain the Library tab selection; practice steps never become hidden sibling tabs.
- `(student)/history.tsx` and `(student)/account.tsx` complete the shell. Use the visible label **Score history** even though the stable path is `/history`.
- Keep reusable `PreviewScreen`, navigation links, and styles under `src/components/`, outside the route directory. Route files supply explicit copy and links; do not build a screen registry, workflow engine, state store, or domain layer for static screens.
- One tab implementation serves mobile and web. Web also uses real Router links, visible keyboard focus, and a centered readable content column; a custom desktop navigator is unnecessary.
- UI flow: Welcome -> Library -> Preparation -> Session -> Report -> Library; tabs reach Score history and Account. Runtime state consists solely of Router navigation state.

### PR #62 integration boundary
The read-only account reference uses SDK 58, `src/app`, a root Stack, and `(student)` Tabs. Reuse those conventions, app scheme `casestudytech`, and native identifiers `com.casestudytech.student` to limit later reconciliation. Do not copy session restoration, `Stack.Protected`, sign-in routes, token stores, Google modules, EAS profiles, or account configuration.

The reference has both root and `(student)` index routes and flat hidden practice tabs. Explicit `/library` and its child stack avoid an ambiguous `/` and keep the practice path selected under Library. On the account PR's later rebase, reconcile package/config/lock/layout changes deliberately, attach its auth guard around `(student)`, and update its post-login redirect to `/(student)/library`. Its former preparation/session/report paths need explicit remapping; this branch does not modify PR #62 or promise conflict-free merging.

## Stack & Dependencies
- **Runtime:** Node 24 LTS (at least 24.3.0), npm, Expo `~58.0.17`, React and React DOM `19.3.0`, React Native `0.88.0`, Expo Router `~58.0.25`, React Native Web `^0.21.4`.
- **Router companions:** expo-constants `~58.0.13`, expo-linking `~58.0.14`, expo-status-bar `~58.0.4`, react-native-safe-area-context `~5.10.1`, react-native-screens `~4.30.0`. Resolve SDK packages with `npx expo install`; validate with `npx expo install --check`.
- **Type/lint:** TypeScript `~6.0.3`, @types/react `~19.3.0`, ESLint `^10.13.0`, @eslint/js `^10.0.1`, typescript-eslint `^8.72.0`, matching the reference. Extend `expo/tsconfig.base`, enable strict mode, and prohibit explicit `any`.
- **Behavior tests:** Jest 30, jest-expo **58.0.12**, @react-native/jest-preset **0.88.0**, @testing-library/react-native **14.1.0**, test-renderer **1.3.0**, and Jest type definitions. SDK 58 Router requires RNTL 14+ and async test helpers. These versions have compatible published peer ranges with React 19.3/RN 0.88. Resolve other test-only peers normally and lock them; no `--force` or `--legacy-peer-deps`.
- Prefer the supported Jest Expo preset over the reference's Vitest-only setup: the shell needs actual native component and Router integration coverage. Do not add deprecated `react-test-renderer` or a hand-mocked Router to make tests pass.
- Commit `package-lock.json`; `npm ci` is the clean-install contract. Small patch resolution changes are acceptable only within SDK 58 and after compatibility/check evidence; do not opportunistically upgrade SDK or add optional UI/native peers.
- **Data store:** none. No application-level network or account/AI SDK dependency. Expo's own bundled platform internals are not application storage behavior.

### ADR-017 (proposed): Expo for the universal student client
- **Context:** Workspace defaults use Next.js, while clarified issue #17 requires shared native Android/iOS and web navigation.
- **Decision:** Use the existing account work's Expo SDK 58 / React Native / Expo Router stack for this student client.
- **Alternatives:** A separate Next.js web app duplicates navigation and cannot supply the native shell; copying the account application couples shell review to unfinished auth.
- **Consequences:** One local UI codebase and compatible integration seams; give up Next.js server rendering and accept Expo's SDK compatibility constraints and web/native verification needs.
- **Revisit:** The student web product gains a demonstrated server-rendering requirement. Lead should retain this project decision with the feature; no shared-memory ADR edit is needed here.

## Deployment Target
- **Cloud/platform:** none for this feature; local browser, Android emulator, and macOS iOS simulator only. The existing project discovery includes a GCP architecture image, but this spec explicitly excludes deployment.
- **Compute/runtime:** local Expo Metro development server; generated native debug projects only when required by the available emulator client. Web output is a single-page export, not a deployed service.
- **IaC/CI:** no cloud resource, EAS account, paid build, workflow, or release distribution change. Generated `android/`, `ios/`, `.expo/`, `dist/`, coverage, dependencies, and local environment files are ignored in `apps/student/.gitignore`.
- **Guidance skill:** n/a; no cloud design or provisioning.

## Data Model
No business entities, input fields, scores, client records, stored identifiers, route parameters, or retained student content. Static copy and literal destination paths are the complete UI data. Do not add fake fixtures to populate unfinished behavior.

## API Contract
No HTTP/RPC API or backend address. Public navigation contract:

| Screen | URL | Route file under `src/app/` |
| --- | --- | --- |
| Welcome | `/` | `index.tsx` |
| Library | `/library` | `(student)/library/index.tsx` |
| Preparation | `/library/preparation` | `(student)/library/preparation.tsx` |
| Session | `/library/session` | `(student)/library/session.tsx` |
| Report | `/library/report` | `(student)/library/report.tsx` |
| Score history | `/history` | `(student)/history.tsx` |
| Account | `/account` | `(student)/account.tsx` |

Use `Link` from `expo-router`, with absolute destinations and accessible labels. Follow `ui.md` exactly for headings, preview notice, body copy, forward actions, and explicit backward links. Backward links work when a screen opens directly without prior history. Each route renders immediately and independently; there is no prerequisite session or auth state. A not-found route is optional; if included, use `ui.md` fallback copy and a working Library link.

### UI and accessibility contract
Every screen displays **Navigation preview** and the exact shared notice from `ui.md`. Welcome's forward action is **Explore the preview**; main tab order is Library, Score history, Account. The reusable frame provides one clear primary heading, safe-area-aware scrollable content, wrapping text/actions, and targets at least 44 logical units high. Avoid duplicate top insets under Stack headers. Web links retain anchor semantics and visible focus; tab selection includes a non-color cue. Do not clip long labels or cap text scaling. Verify title/focus behavior on route changes rather than assuming native or web accessibility from component choice alone. No fake user, client, score, chart, account control, completion message, or loading state is needed.

## Security & Privacy
There is no threat-model artifact at planning time and no new sensitive-data or permission surface. `app.config.ts` contains only public identity/platform/Router configuration and Metro web `output: single`; no env dependency, service URL, API key, Google plugin, token storage, or EAS project ID. Install only the Router configuration plugin. No fetch, WebSocket, analytics, external font/icon download, browser storage, native storage adapter, or console logging of content. Local Metro asset traffic is development tooling, not application data access. Review source/config/lock and all three generated export artifacts for credential patterns and unintended account/AI integrations; investigate scan hits rather than treating a string match alone as proof. If implementation creates a real security trigger, stop that expansion and route it to Lead for specialist review.

## Observability
No production telemetry, metrics, tracing, or service health endpoint is appropriate for a local static shell. Use deterministic test output, Expo compatibility checks, export logs, and captured runtime evidence. Record failures and unavailable platforms in `verification.md`, including command, environment, result, and evidence location. Do not suppress native errors to present an apparent successful launch.

## Testing Strategy
- Write route behavior tests first in `apps/student/__tests__/navigation.test.tsx`, outside `src/app`. Use `jest-expo` and `expo-router/testing-library` with the actual route directory or actual imported route/layout components; mock native boundaries only through the supported preset. Await `renderRouter`, user actions, and Router helpers as required by SDK 58.
- Prove Welcome -> Library -> Preparation -> Session -> Report -> Library through actual accessible actions and rendered destination headings. Prove both other tabs, only three main tab destinations, and Library selection throughout its child stack. Assert each route's preview disclosure and absence of functioning account/practice controls.
- Parameterize direct loading of all seven URLs and explicit backward navigation from preparation/session/report without navigation history. Do not substitute source-text checks, screenshots of JSX, route-array counts, or snapshots for navigation behavior.
- Real browser smoke covers every route, direct loading, browser back, keyboard navigation/activation, visible focus/selection, readable layout at 320px and 200% zoom, and screenshots required by `ui.md`. Component tests do not prove browser semantics.
- Run `npm ci`, lint, strict typecheck, non-watch tests, and `npx expo install --check`; diagnose dependency problems with Expo Doctor as needed. Document scripts `start`, `web`, `android`, `ios`, `lint`, `typecheck`, `test`, `export:web`, `export:android`, and `export:ios`. Exports use separate `dist/<platform>` directories.
- Android: start available emulator, launch the app with matching SDK 58 Expo Go or a local generated debug build if needed, then record the actual shell and child-path navigation. No account credentials or paid build.
- iOS: document a minimal macOS/Xcode simulator handoff (`npm ci`, checks, `npm run ios`, or `npx expo run:ios` for a local debug build), then capture actual launch evidence when a Mac is available. Windows cannot run the iOS simulator; no remote Mac is configured. An iOS bundle export is compile evidence only and **does not satisfy** the simulator-launch criterion. Keep AC1 partially unverified until actual iOS runtime evidence arrives; no speculative CI or paid remote infrastructure.

### Acceptance evidence (1:1 with spec)
1. **AC1:** real web reachability plus Android emulator launch and iOS simulator launch, each separately recorded. Missing iOS evidence leaves this criterion unchecked and the platform limitation explicit.
2. **AC2:** clean `npm ci` followed by passing lint, strict typecheck, and meaningful route behavior tests; record test totals and command results.
3. **AC3:** source/config/dependency/export review establishes no credentials, account/AI SDK integration, application network access, or retained content; record scan scope and resolved findings.

## Risks & Trade-offs
- **PR overlap:** `apps/student` is new on dev but already exists in PR #62. Matching runtime and `(student)` naming limits drift; its later rebase must reconcile paths, lockfiles, and auth layouts. Duplicating the whole account app now creates avoidable long-term coupling.
- **Native evidence:** Windows supports available Android tooling but not iOS simulation. Deliver a reviewable Mac handoff and preserve the unverified criterion; export success must not become a launch claim.
- **Dependency drift:** SDK 58 changes test APIs and package peers. Use matching official docs, published peer metadata, a lockfile, and actual behavior tests; avoid legacy test-renderer recipes.
- **Navigation trade-off:** a real Library stack changes unmerged flat reference URLs but gives correct tab selection and back behavior; explicit mapping is required during later auth integration.
- **Scope trade-off:** generic React Native styling and shared JS Tabs meet the shell requirement with little code; final Figma fidelity, platform-specific desktop navigation, domain services, and auth belong to later issues.

## Skills Consulted
`system_design.md`, `software_architecture.md`, and `testing.md` from `C:/Users/sandy/Desktop/dev/skills/`.

## Official references checked
- [Expo SDK 58 compatibility and install guidance](https://docs.expo.dev/versions/v58.0.0/): React 19.3 / RN 0.88 and SDK-aware package installation.
- [SDK 58 Stack](https://docs.expo.dev/versions/v58.0.0/sdk/router/stack/) and [SDK 58 Link](https://docs.expo.dev/versions/v58.0.0/sdk/router/link/): navigator and anchor APIs.
- [SDK 58 safe areas](https://docs.expo.dev/versions/v58.0.0/sdk/safe-area-context/): cross-platform insets.
- [Router notation](https://docs.expo.dev/router/basics/notation/) and [JavaScript tabs](https://docs.expo.dev/router/advanced/tabs/): groups, paths, and built-in tab layout.
- [Router testing, explicitly SDK 58+](https://docs.expo.dev/router/reference/testing/) and [Jest configuration](https://docs.expo.dev/develop/unit-testing/): RNTL 14+, awaited helpers, and Jest Expo preset.
- [Expo documentation index](https://docs.expo.dev/llms.txt) and [manual Router setup](https://docs.expo.dev/router/installation/): current entry/configuration and optional peers. SDK overview URL timed out; the versioned Stack/Link pages loaded successfully.
