# Student access and accounts (#25/#26/#46)
Branch: feature/4-access-accounts · PR #62 · Lead run: 2026-11-20 · Status: building
Intent: Google-only sign-in/sign-out on the #17 shell; protected routes; deletion with confirmation; CI green.
Change surfaces: auth (client session, Google adapters), routing guards, Account screen, deletion UI, lockfile/test runner.
Likely touch points: apps/student/src/app/**, src/auth/**, app.json + app.config.ts, package.json/lock, tests/.
Coordination: sits on top of merged #71 (017-cross-platform-scaffold). PR #99 (#18) is stacked on this branch; rebase it after #62 merges.
