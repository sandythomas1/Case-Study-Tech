# Student application

Expo/React Native with TypeScript strict mode and platform-specific Google sign-in/token storage adapters. `npm ci`, then `npm run typecheck`, `npm run lint`, `npm test`, and `npm start`.

Supply public OAuth client IDs and the HTTPS accounts API address through `.env.example`; never add API keys, provider secrets or tokens. Web uses the official Google Identity Services button; native uses Google Sign-In in a custom development build. Expo Go cannot supply that native module. Refresh tokens use device SecureStore on native and memory on web; ID tokens live in memory. Closing/reloading a web tab ends that local session.

`eas.json` only defines internal development/preview and iOS simulator builds. There is no public App Store profile. On macOS or an authorized EAS account, configure the project's OAuth clients and native signing first, then create an internal build. Do not submit to the public App Store under the Google-only MVP. Public distribution needs a documented applicable education exception or an Apple-compliant equivalent sign-in option.

Internal build configuration is not an installed TestFlight/internal build. This Windows workspace cannot verify an iOS simulator or Apple signing. Core auth tests isolate Google/transport/storage boundaries; they do not prove native sign-in or actual account deletion against a deployed service.
