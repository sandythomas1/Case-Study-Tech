# Account credentials and ownership

Date: 2026-10-21. Scope: #4, #25, #26, #46. Implementation decision; live deployment remains pending.

## Decision

Use Google sign-in only and a provider-neutral account service backed by Identity Platform. Keep the Identity Platform API key on the server to satisfy RC-06's strict prohibition on client API keys. Native obtains a Google ID token from Google Sign-In; web uses Google Identity Services. The server exchanges it using a fixed Google provider and configured request URI. Public OAuth client IDs are not service credentials.

The app keeps Firebase ID tokens in memory, stores only refresh tokens in native SecureStore, and uses memory-only web persistence. Refresh is performed through the backend and the resulting identity is verified before protected UI appears. Session generation checks prevent late sign-in/refresh responses from restoring a signed-out account.

API Gateway validates protected-route JWTs and invokes a private Cloud Run backend. The backend additionally verifies the original Firebase token, revocation and Google provider. It supports the forwarded authorization header because gateway backend authentication replaces Authorization. It never treats decoded gateway Userinfo or a caller-provided UID as authentication.

Scores are read only beneath the verified owner's collection. Direct Firestore rules permit the same active Google owner and deny all client writes. Account deletion writes a durable denial marker before provider revocation so access fails closed during outages. Cleanup is retryable and retains its completed marker beyond the maximum normal ID-token lifetime.

## Tradeoffs and remaining verification

Backend exchange adds a network hop and requires abuse controls for unauthenticated exchange/refresh routes. Memory-only web sessions require fresh sign-in after reload. Native Google sign-in requires custom native builds and configured OAuth clients; Expo Go is insufficient. The completed-marker retention and future score-writer transaction guard must remain aligned.

This decision does not grant deployment authorization, establish OAuth configuration, validate clinical grading, or claim Figma fidelity. Live token exchange, gateway IAM, deployed rules, native signing and device flows still need evidence.

## Primary references

- [Identity Platform credential exchange](https://docs.cloud.google.com/identity-platform/docs/reference/rest/v1/accounts/signInWithIdp)
- [Firebase Auth REST exchange and refresh](https://firebase.google.com/docs/reference/rest/auth)
- [API Gateway Firebase authentication](https://docs.cloud.google.com/api-gateway/docs/authenticating-users-firebase)
- [Gateway backend authentication and forwarded identity](https://docs.cloud.google.com/api-gateway/docs/authenticate-service-account)
- [Expo Google authentication and native builds](https://docs.expo.dev/guides/google-authentication/)
