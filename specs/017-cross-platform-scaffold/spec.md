# Spec: Cross-platform student application scaffold

> Phase: Specify Â· Status: clarified Â· Owner: Lead Â· Date: 2026-10-30

## Problem
Frontend stories need a shared, runnable foundation on dev. The earlier scaffold exists only inside the unmerged account PR #62, coupling navigation review to live authentication work.

## Goals
- One strict TypeScript React Native project starts on web, Android, and iOS.
- Students can explore clearly marked placeholders for Welcome, Library, Preparation, Session, Report, Score history, and Account.
- Local lint, typecheck, and meaningful unit tests pass from a locked installation.

## Non-goals
- Authentication, account data, conversations, grading, storage, or backend integration.
- Figma fidelity (#58), release distribution (#50), or deployment.
- Modifying PR #62 or claiming its authentication is complete.

## User story
As a frontend developer, I can run and extend one navigation shell across all three platforms without credentials or live services.

## Functional requirements
1. Use one Expo Router / React Native codebase with TypeScript strict mode.
2. Provide all seven named routes, with bottom tabs on mobile and equivalent navigation on web. Library, Score history, and Account are top-level destinations; Preparation, Session, and Report form the nested practice path.
3. Every screen must clearly communicate that it is a preview, with no simulated scores or claims of functioning sign-in/practice.
4. Include only public configuration, with no API keys, service credentials, network calls, or retained student content.
5. Provide reproducible lint, typecheck, unit-test, platform-export, and local startup commands.

## Non-functional requirements
- Accessible names, visible focus/selection, safe-area handling, keyboard access on web, readable narrow layouts.
- Locked dependencies; generated native projects and local environment files ignored.
- No new cloud or paid build requirements.

## Acceptance criteria
- [ ] Web starts and every shell destination is reachable; Android emulator starts and shows the shell; iOS simulator starts and shows the shell.
- [x] Lint, strict typecheck, and behavior tests pass following npm ci.
- [x] Source/configuration and exported bundles contain no credentials; no account/AI SDKs or data access are introduced.

## References
- Issue #17; RC-06, RC-14, DD-06; SDD sections 4.4, 5.1, 6.2.
- PR #62 owns account integration; rebasing it after this scaffold will require reconciling apps/student.
- Existing account implementation: C:/Users/sandy/Desktop/dev/Case-Study-Tech-issue4 (read-only reference).
- No project constitution exists on dev.
