# Student navigation preview

One Expo SDK 58 / React Native / strict TypeScript application for web, Android, and iOS. All seven screens are navigation previews. Practice, scores, and accounts are unavailable; there are no credentials, services, input fields, or saved student content.

## Install and check

Use Node 24 LTS (24.3.0 or newer in the 24.x line) and npm. Run these commands from `apps/student`:

```sh
npm ci
npm run lint
npm run typecheck
npm test
npx expo install --check
npx expo-doctor
```

`package-lock.json` is the installation contract. Use `npx expo install` for SDK-aware dependency changes and rerun checks. Jest Expo and React Native Testing Library 14 exercise the actual route tree; test files live outside `src/app`.

Validate lockfile changes in Linux CI as well as locally. The initial npm 11.6.2 lockfile omitted two optional WASM peers required by npm 11.19.1 in CI; regenerating metadata with that npm version in an isolated directory repaired it without changing existing package versions.

## Run locally

```sh
npm start
npm run web
npm run android
npm run ios
```

`start` opens the Metro CLI. Use the platform commands individually to open the corresponding client. Web requires a local browser. Android requires Android Studio, its SDK/platform tools, and a running emulator. iOS requires a Mac, Xcode command-line tools, and an installed simulator. Windows can serve and export the iOS bundle but cannot launch its simulator.

Use an Expo Go client supporting SDK 58. If the emulator/simulator client does not support SDK 58, build a local debug client instead:

```sh
npx expo run:android
# On macOS with Xcode and a simulator:
npx expo run:ios
```

These commands generate ignored native folders. No EAS account, cloud build, credentials, or paid service is required. For a Mac handoff: clone the feature branch, install Node 24 and Xcode, run `npm ci` and the checks above, start an iOS simulator, then run `npm run ios` (or the local debug build fallback). Verify the seven screens and practice path on the simulator and record its actual launch separately from export results.

## Navigation

| Screen | Path |
| --- | --- |
| Welcome | `/` |
| Library | `/library` |
| Preparation | `/library/preparation` |
| Session | `/library/session` |
| Report | `/library/report` |
| Score history | `/history` |
| Account | `/account` |

Welcome leads to the three-tab student area. Preparation, Session, and Report stay within the Library stack. Explicit backward links work when a screen opens directly. Native hardware/gesture back and browser back use Router history. The native URL scheme is `casestudytech` (for example, `casestudytech://library/session`).

## Export

```sh
npm run export:web
npm run export:android
npm run export:ios
```

Outputs are ignored under `dist/<platform>`. Web uses a single-page export; a future host must serve `index.html` for application paths. Exports prove bundle compilation only. They do **not** prove native simulator/emulator launch or native UI behavior.

## Public configuration and extension boundary

`app.json` contains public app identity and Router/platform configuration only. No environment variables are needed. Never put credentials or secrets in app configuration or `EXPO_PUBLIC_*` variables: these values are visible to clients. Local environment files, dependencies, Expo state, exports, and generated native projects are ignored.

Keep reusable UI outside `src/app`; every file inside that directory is a route or layout. There is no competing `App.tsx` entry, state store, backend endpoint, or configuration service.

The unmerged account PR #62 uses overlapping `apps/student` files. Its later rebase must reconcile dependencies, lockfile, config, root layout and `(student)` layout, place its authentication guard around `(student)`, and redirect successful entry to `/(student)/library`. Its old flat Preparation/Session/Report paths need remapping to the nested Library paths. This scaffold does not modify or complete that account integration.
