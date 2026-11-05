# iOS account verification on Mac

Apple development is owned by Sandy on Mac. This handoff does not claim an installed iOS build or close #50/#4. Use the shared source on `feature/4-access-accounts`; current acceptance criteria remain on [#50](https://github.com/sandythomas1/Case-Study-Tech/issues/50) and [#25](https://github.com/sandythomas1/Case-Study-Tech/issues/25).

## Identities and prerequisites

- Firebase project: `casestudy-tech-dev-2e03d0`.
- iOS Firebase app: `1:613104664964:ios:ca6ab7a9e5c7f984baddd1`.
- Bundle ID: `com.casestudytech.student`; app scheme: `casestudytech`.
- Expo SDK 58, React Native 0.88, Node 24.11.1 used for existing local verification. Use the lockfile and SDK-compatible installs.
- Xcode and its command-line tools for local compilation; an Expo account and the intended Apple Developer team/signing for physical internal distribution. No public App Store submission.
- Create the actual Google web and iOS OAuth clients in this project's Google Auth Platform. The iOS client must use the bundle ID above. Configure Google as the only Identity Platform provider. The native Google SDK uses the web client ID as server audience and the iOS client ID for its native flow.

## Build from the shared project

Check out the feature branch, then run these from `apps/student`:

```sh
npm ci
npm test
npm run typecheck
npm run lint
npx expo-doctor
```

Set only public configuration in a local, ignored `.env.local`:

```dotenv
EXPO_PUBLIC_API_URL=https://accounts-7tnmor5w.uc.gateway.dev
EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=<actual web OAuth client ID>
EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID=<actual iOS OAuth client ID>
GOOGLE_IOS_URL_SCHEME=<reversed iOS OAuth client ID>
```

Obtain the exact reversed client ID from Google's iOS client configuration. Do not enter API keys, OAuth client secrets, service-account keys or refresh tokens. No Firebase API key or `GoogleService-Info.plist` needs to be bundled by this account flow. The secret API key stays in the private backend.

`app.config.ts` adds the Google URL-scheme config plugin when `GOOGLE_IOS_URL_SCHEME` is set. Native directories are generated: configure through Expo and do not hand-edit generated Xcode files. Use `npx expo run:ios` for the simulator. Native Google Sign-In needs the development binary and is not proven by Expo Go or a Hermes export.

For physical internal testing, sign in with `npx eas-cli@latest login`, associate the intended Expo project, register the test devices, and build with `npx eas-cli@latest build --platform ios --profile development`. The existing development/preview profiles use internal distribution; `ios-simulator` is a separate simulator-only profile. Supply the same public environment settings to the selected EAS build environment. Confirm Apple team/device provisioning during this build. Use an appropriate signed internal profile for device installs; simulator artifacts cannot be installed on an iPhone.

See [Expo local development](https://docs.expo.dev/guides/local-app-development/) and [internal distribution](https://docs.expo.dev/build/internal-distribution/) for the current signing/device workflow.

## Evidence to record in GitHub

Use synthetic scores and test accounts; never paste credentials, tokens, private certificates, session content or other students' information into GitHub.

- Commit SHA, Xcode/SDK/device or simulator version, build profile and internal build ID/link, and installation result.
- Actual Google sign-in opens the protected Library. A sign-in failure offers retry. No other sign-in method is presented.
- Sign out from Account, then attempt deep links/back navigation to Library/History/Account. Protected views must stay inaccessible until sign-in.
- Reopen the app and verify secure-session restoration/refresh; do not inspect or publish stored token values.
- With two test owners, each sees only its own synthetic scores.
- Cancel Delete account and verify the session remains usable. Confirm Delete account and verify immediate sign-out, denied old-session access and eventual actual account/score removal through the deployed worker.
- Record any failure honestly; check acceptance boxes only after the actual result. An installed core-flow demonstration is required for #50. Hermes compilation and the Windows Android build are separate evidence.

Google-only iOS remains internal/TestFlight for this MVP. Public App Store distribution needs an applicable education exception or an Apple-compliant equivalent sign-in option as documented in the software design plan.
