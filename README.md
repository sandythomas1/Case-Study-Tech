# Case-Study-Tech

An application for students to practice counseling with simulated clients and receive formative feedback.

## Student application

The [shared React Native / Expo project](apps/student/README.md) contains a navigation preview for web, Android, and iOS. It does not implement sign-in, counseling sessions, scores, or account data.

```sh
cd apps/student
npm ci
npm run lint
npm run typecheck
npm test
npm run web
```

See the app README for native startup and export commands, tool requirements, and configuration boundaries. iOS simulator startup requires macOS and Xcode. Build/export success alone does not establish an installed native app works.

## Feature evidence

- [Issue #17 specification](specs/017-cross-platform-scaffold/spec.md)
- [Architecture and integration notes](specs/017-cross-platform-scaffold/plan.md)
- [Verification](specs/017-cross-platform-scaffold/verification.md)
- [Review](specs/017-cross-platform-scaffold/review.md)

The separate account implementation in [PR #62](https://github.com/sandythomas1/Case-Study-Tech/pull/62) overlaps `apps/student/` and will need to reconcile this scaffold when rebased. It owns authentication and route protection; the scaffold introduces no access to student data.
