# Student application

One Expo SDK 58 / React Native / strict TypeScript application for web, Android, and iOS. Students sign in with Google only, reach the protected practice screens, sign out, and can request account deletion. Library, Preparation, Session, Report, and Score history are still navigation previews: practice and scores are unavailable, and there are no input fields or saved student content.

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

`package-lock.json` is the installation contract. Use `npx expo install` for SDK-aware dependency changes and rerun checks. Jest Expo and React Native Testing Library 14 exercise the actual route tree; test files live in `tests/`, outside `src/app`. Route tests replace `src/auth/runtime` with a real session wired to a fake accounts API and an in-memory store (`tests/support/auth.ts`), and replace the native Google module, so they make no network calls.

Write lockfile changes with CI's npm version, not a local npm: `npx -y npm@11.19.1 install --ignore-scripts --no-audit --no-fund`, then confirm `npx -y npm@11.19.1 ci`. Local npm 11.6.2 omits two optional WASM peers (`@emnapi/core`, `@emnapi/runtime`) that `npm ci` in CI requires.

## Configuration

Copy `.env.example` to `.env` and supply the public OAuth client IDs and the HTTPS accounts API address. Never add API keys, provider secrets, or tokens: every `EXPO_PUBLIC_*` value is visible to clients. `.env` files are ignored; only the template is tracked.

`app.json` contains the reviewed public app identity and Router/platform configuration only. `app.config.ts` is a thin layer over it that appends the `expo-secure-store` plugin and, when `GOOGLE_IOS_URL_SCHEME` is set, the Google Sign-In plugin with that public reversed client ID.

Web uses the official Google Identity Services button. Android and iOS use the native Google Sign-In module, which needs a custom development build; Expo Go cannot supply it. Refresh tokens use device SecureStore on native and memory on web; ID tokens live in memory. Closing or reloading a web tab ends that local session.

## Run locally

```sh
npm start
npm run web
npm run android
npm run ios
```

`start` opens the Metro CLI. Use the platform commands individually to open the corresponding client. Web requires a local browser. Android requires Android Studio, its SDK/platform tools, and a running emulator. iOS requires a Mac, Xcode command-line tools, and an installed simulator. Windows can serve and export the iOS bundle but cannot launch its simulator.

For native Google sign-in, build a local debug client instead of Expo Go:

```sh
npx expo run:android
# On macOS with Xcode and a simulator:
npx expo run:ios
```

These commands generate ignored native folders. For iOS, follow [the Mac handoff](../../docs/ios-mac-handoff.md).

## Navigation and access

| Screen | Path | Access |
| --- | --- | --- |
| Welcome | `/` | Public |
| Sign in | `/sign-in` | Public |
| Library | `/library` | Signed in |
| Preparation | `/library/preparation` | Signed in |
| Session | `/library/session` | Signed in |
| Report | `/library/report` | Signed in |
| Score history | `/history` | Signed in |
| Account | `/account` | Signed in |

The root layout uses `Stack.Protected`. Signed-out visits to any `(student)` route go to Sign in; signed-in visits to Welcome or Sign in go to Library. On launch the app checks a saved sign-in before showing any screen, so a returning student's deep link is kept and no protected screen appears early. Welcome leads to Sign in. Preparation, Session, and Report stay within the Library stack, with explicit backward links when a screen opens directly. The native URL scheme is `casestudytech` (for example, `casestudytech://library/session`).

The Account screen signs out (clearing the saved sign-in) and requests deletion behind an explicit confirmation. After the service accepts the request, the student is signed out and Sign in confirms the request. If the request fails, the message stays inside the confirmation.

## Export

```sh
npm run export:web
npm run export:android
npm run export:ios
```

Outputs are ignored under `dist/<platform>`. Web uses a single-page export; a host must serve `index.html` for application paths. Exports prove bundle compilation only. They do **not** prove native simulator/emulator launch or native UI behavior.

## Internal builds

`eas.json` only defines internal development/preview and iOS simulator builds. There is no public App Store profile. On macOS or an authorized EAS account, configure the project's OAuth clients and native signing first, then create an internal build. Do not submit to the public App Store under the Google-only MVP. Public distribution needs a documented applicable education exception or an Apple-compliant equivalent sign-in option.

Windows native build verification used a short app checkout at `C:/c4`, JDK from Android Studio, the existing Android SDK, and official Ninja 1.13.2 downloaded separately with its GitHub release checksum verified. Set `CST_NINJA_PATH` to that binary and run `android/gradlew.bat -p android assembleRelease --no-daemon -PreactNativeArchitectures=x86_64 --init-script scripts/windows-cmake.gradle` after `npx expo prebuild --platform android --no-install`. The optional init script sets Ninja and a 240-character object-path limit across native modules. A long checkout can still exceed native tool limits.

That produces a local test artifact using the template debug signing identity. It is not a student release or a production signing configuration. Rebuild after setting the actual public API/OAuth configuration before Google sign-in verification. See [the integration evidence](../../docs/implementation/issue-4-live-verification.md) for recorded results and remaining gates.

## Extension boundary

Keep reusable UI outside `src/app` (`src/components`, `src/auth`); every file inside `src/app` is a route or layout. There is no competing `App.tsx` entry.
