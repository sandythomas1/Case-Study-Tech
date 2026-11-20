# Review — issue #17 scaffold

Date: 2026-10-30. Base: dev aa6ea60. Scope: apps/student, local verification harnesses, CI and feature documentation.

## Findings and dispositions

| Finding | Severity | Disposition |
| --- | --- | --- |
| Router asChild drops the Pressable style callback, leaving white link text on a light background, no minimum target, and no custom focus ring. | Blocking UX | Fixed. Supply a flattened style object with explicit pressed/focus state. New real-route regression test first failed, then passed. Final browser focus/layout tests pass; Android evidence is recorded in verification.md. |
| Zod upstream HIGH advisory in optional installed Expo development-plugin tooling. | Contextual LOW | Independently traced by security-reviewer: no demonstrated student-input/unauthenticated HTTP path; plugin/MCP prerequisites absent. No supported patch currently available. Track #61 and reassess if tooling boundary changes; details in threat-model.md. |
| deepmerge LOW advisory in repository-controlled Expo/Jest configuration. | LOW | No untrusted application merge path found. Track #61; no unsupported major override or forced downgrade. |
| iOS simulator runtime evidence is unavailable on Windows. | Acceptance gap | Leave issue's cross-platform-start criterion unchecked; Mac instructions supplied. An iOS Hermes export is not simulator acceptance. Open a draft PR for concrete review. |
| App directory overlaps unmerged account PR #62. | Integration follow-up | Preserve existing account work; document explicit path/guard/lockfile reconciliation on its later rebase. No account service access or auth bypass introduced. |
| Initial Windows-generated lockfile omitted optional WASM peer entries required by CI's newer npm, blocking Linux npm ci. | Blocking verification | Regenerated metadata with CI's npm11.19.1 in isolation; adds exactly two nodes without changing or removing existing package versions. Clean install/lint/types/tests rerun; hosted CI confirms Linux installation and exports. |

## Review evidence and limits
- Architecture and UX design reviews completed independently before implementation. Security review independently inspected source, lockfile, CI, and toolchain reachability; no blocking security finding.
- QA agent hit a usage limit before producing final verification. Sandy instructed “continue”; Lead completed actual local browser/native verification and final review without further specialist dispatches. Final screenshot review is Lead review, not a claimed independent UX sign-off.
- Read all new route/layout/component source and behavior tests. Seven explicit local routes, no competing app entry, state store, network integration, data entry, or persistence. TypeScript strict and ESLint pass.
- Local browser tests use an isolated Chromium profile and the production web export. Personal Edge access was denied; no personal browser profile or private state was used.
- CI runs ordinary unprivileged PR checks, has read-only repository permissions, disables credential persistence, pins official actions and supplies no secrets. Workflow YAML parsed locally. Actual hosted execution is reported separately after PR creation.
- Source/configuration and all platform export files were scanned for common credential formats with no matches (98 files). This is bounded pattern evidence plus source/config review, not a universal secret-detection guarantee.
- No backend/permission/data-access changes, clinical rules, assessment policy, deployment, or protected-branch merge.

## Re-review — 2026-11-19 (Expo 58.0.26 patch, dev sync)

| Finding | Severity | Disposition |
| --- | --- | --- |
| e4ddd04 regenerated the lockfile with the local npm 11.6.2 and dropped the @emnapi/core and @emnapi/runtime 1.11.3 optional-peer nodes again. Hosted CI run 44463641151 failed at npm ci. | Blocking verification | Fixed in 4cd1407: regenerated with npm 11.19.1 in isolation, 2 nodes added, 0 removed, 0 version/integrity changes. Clean npm ci and all local checks and exports pass. |
| npm audit after the patch: 0 high/critical; 22 moderate (20 non-dev) from 2 upstream advisories (glob, minimatch) in Expo build tooling. | LOW (contextual) | Accepted: the build/file-matching tooling is not reachable from student input in a static shell with no network or data paths. Still tracked by #61. |
| iOS simulator proof cannot be produced on Windows. | Acceptance gap | Owner decision 2026-11-19: split into #103; AC1 narrowed to web and Android. |
| Runtime regression risk from the dependency bump. | Check | QA re-verification: 6/6 browser tests (web screenshots byte-identical to ed8a6a2), 11/11 Android checkpoints, 0 credential-pattern matches across 101 files. No regressions. |

No open blocking findings. The diff since the last review adds no app source, UI or permission change, so security/UX/architect re-reviews were not re-engaged. The project `policy-reviewer` agent can't be dispatched from this session (it isn't in the agent roster here); the owner's Deep review covers it.
