# Student application

Expo/React Native with TypeScript strict mode and platform-specific Google sign-in/token storage adapters. `npm ci`, then `npm run typecheck`, `npm run lint`, `npm test`, and `npm start`.

Supply public OAuth client IDs and the HTTPS accounts API address through `.env.example`; never add API keys, provider secrets or tokens. Web uses the official Google Identity Services button; native uses Google Sign-In in a custom development build. Expo Go cannot supply that native module. Refresh tokens use device SecureStore on native and memory on web; ID tokens live in memory. Closing/reloading a web tab ends that local session.

`eas.json` only defines internal development/preview and iOS simulator builds. There is no public App Store profile. On macOS or an authorized EAS account, configure the project's OAuth clients and native signing first, then create an internal build. Do not submit to the public App Store under the Google-only MVP. Public distribution needs a documented applicable education exception or an Apple-compliant equivalent sign-in option.

Internal build configuration is not an installed TestFlight/internal build. This Windows workspace cannot verify an iOS simulator or Apple signing. Core auth tests isolate Google/transport/storage boundaries; they do not prove native sign-in or actual account deletion against a deployed service.

Windows native build verification used a short app checkout at `C:/c4`, JDK from Android Studio, the existing Android SDK, and official Ninja 1.13.2 downloaded separately with its GitHub release checksum verified. The shared SDK and Windows long-path registry setting were not changed. Set `CST_NINJA_PATH` to that modern binary and run `android/gradlew.bat -p android assembleRelease --no-daemon -PreactNativeArchitectures=x86_64 --init-script scripts/windows-cmake.gradle` after `npx expo prebuild --platform android --no-install`. The optional init script sets Ninja and a 240-character object-path limit across native modules. Expo's root plugin defaults this limit to 1024; the resulting CMake cache must show 240 for this workaround. Expo also exposes `expo.android.cmakeObjectPathMax` as a Gradle property, but the recorded build used the init script above. A long checkout can still exceed native tool limits even with hashing.

This produces a local test artifact using the template debug signing identity. It is not a student release or a production signing configuration. The audit gate in #61 still applies. Rebuild after setting the actual public API/OAuth configuration before Google sign-in verification. For iOS, follow [the Mac handoff](../../docs/ios-mac-handoff.md).

The local APK installed and launched successfully on Android 36. Welcome and five protected deep links passed anonymous UI checks; Google sign-in remains unverified. See [the integration evidence](../../docs/implementation/issue-4-live-verification.md) for exact results and remaining gates.
