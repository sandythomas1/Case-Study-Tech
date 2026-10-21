# Accounts environment setup

## Created development resources

- Google Cloud/Firebase project: `casestudy-tech-dev-2e03d0` (project number `613104664964`).
- Firebase web app: `1:613104664964:web:4d551431bea457c6baddd1`.
- Firestore Native `(default)` database: `us-central1`, standard/free-tier at creation.
- Identity Toolkit, Firestore and Firebase Rules APIs enabled. Existing gcloud defaults were not changed.

[Firebase console](https://console.firebase.google.com/project/casestudy-tech-dev-2e03d0/overview) · [Google Auth Platform clients](https://console.cloud.google.com/auth/clients?project=casestudy-tech-dev-2e03d0)

## Pending live setup

Identity Platform initialization returned `BILLING_NOT_ENABLED`. Linking the existing billing account is pending the owner's response; no billing link is assumed. The initial SDK REST request also required `x-goog-user-project: casestudy-tech-dev-2e03d0` for quota attribution; setting that request header resolved the quota-project error without changing global ADC settings.

After authorized billing linkage, initialize Identity Platform, configure Google as the only provider, disable password/anonymous/other providers, and register the actual web/iOS/Android OAuth clients. Web origins must match the real served application. Native client registration must match the iOS bundle ID and Android package/signing certificate. Supply the web client ID as the native server audience and the iOS client ID/URL scheme where required. Do not use placeholder OAuth IDs in a release build.

Keep the Identity Platform API key restricted to Identity Toolkit/Secure Token APIs and provide it to Cloud Run through Secret Manager. The student bundle receives only public client IDs and its HTTPS API address. No service-account JSON keys are needed. Provision service identities with only required Firebase Auth/Firestore access, and a separate gateway invoker identity. Confirm actual IAM with deployment evidence under #18.

`infra/gateway.yaml.template` is a reviewable template, not a deployed gateway. Substitute the explicit project ID and private accounts service URL. Protected routes require Firebase JWTs. The backend still verifies the original forwarded token and deletion state; prevent direct unauthenticated Cloud Run invocation with IAM. Configure origin allowlists, public exchange/refresh abuse limits, and allowlisted operational logging before launch. Implement verified CORS preflight behavior in the final gateway configuration.

Deploying services/rules or running an EAS build requires the relevant authorization and environment configuration; this worktree does not auto-deploy. Schedule the deletion worker hourly with retries and deadline/failure monitoring. Test a synthetic deletion against the deployed environment before accepting the 30-day criterion. The new project's Firestore access must remain denied by default until reviewed rules are applied.

## iOS boundary

Google-only iOS is for internal/TestFlight distribution. `apps/student/eas.json` prepares internal profiles only. Apple developer provisioning, native OAuth clients, and an installed internal build remain necessary to verify #50. No public App Store submission is part of this MVP.
