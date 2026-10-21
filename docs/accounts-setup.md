# Accounts environment setup

## Created development resources

- Google Cloud/Firebase project: `casestudy-tech-dev-2e03d0` (project number `613104664964`).
- Firebase web app: `1:613104664964:web:4d551431bea457c6baddd1`.
- Firestore Native `(default)` database: `us-central1`, standard/free-tier at creation.
- Identity Toolkit, Firestore and Firebase Rules APIs enabled. Existing gcloud defaults were not changed.
- Paid billing enabled on the existing `Firebase Payment` account (verified 2026-10-21); the Firebase project is on the Blaze plan.
- Identity Platform initialized successfully (HTTP 200); configuration readback is `projects/613104664964/config`. Anonymous, email and phone sign-in are disabled.

[Firebase console](https://console.firebase.google.com/project/casestudy-tech-dev-2e03d0/overview) · [Google Auth Platform clients](https://console.cloud.google.com/auth/clients?project=casestudy-tech-dev-2e03d0)

## Billing verification and history

The initial paid upgrade failed with `FAILED_PRECONDITION` / `QuotaFailure`: `Cloud billing quota exceeded`. The owner then explicitly authorized removing Auto-Cloud-Deploy from the billing account and replacing it with CaseStudy Tech. Unlinked `auto-cloud-deploy-500705`, linked `casestudy-tech-dev-2e03d0`, and verified the former has billing disabled and the latter has billing enabled. Auto-Cloud-Deploy's project was not deleted; paid services there may stop because its billing is disabled. No other project's billing association was changed.

The account's five linked projects are now System Design Course, YMAN-Storage-App, resimax, CaseStudy Tech and NBA Predictions. The billing quota blocker is resolved for this setup; no support request was submitted. Recheck the two explicit project IDs without changing global gcloud defaults:

```powershell
gcloud billing projects describe auto-cloud-deploy-500705 --format='value(billingEnabled)'
gcloud billing projects describe casestudy-tech-dev-2e03d0 --format='value(billingEnabled)'
```

Expected readback: `False` for Auto-Cloud-Deploy, `True` for CaseStudy Tech.

## Pending live setup

Identity Platform initialization is complete. Configure Google as the only provider, keep password/anonymous/other providers disabled, and register the actual web/iOS/Android OAuth clients. The SDK REST request requires `x-goog-user-project: casestudy-tech-dev-2e03d0` for quota attribution; setting that header resolved the earlier quota-project error without changing global ADC settings. Web origins must match the real served application. Native client registration must match the iOS bundle ID and Android package/signing certificate. Supply the web client ID as the native server audience and the iOS client ID/URL scheme where required. Do not use placeholder OAuth IDs in a release build.

Keep the Identity Platform API key restricted to Identity Toolkit/Secure Token APIs and provide it to Cloud Run through Secret Manager. The student bundle receives only public client IDs and its HTTPS API address. No service-account JSON keys are needed. Provision service identities with only required Firebase Auth/Firestore access, and a separate gateway invoker identity. Confirm actual IAM with deployment evidence under #18.

`infra/gateway.yaml.template` is a reviewable template, not a deployed gateway. Substitute the explicit project ID and private accounts service URL. Protected routes require Firebase JWTs. The backend still verifies the original forwarded token and deletion state; prevent direct unauthenticated Cloud Run invocation with IAM. Configure origin allowlists, public exchange/refresh abuse limits, and allowlisted operational logging before launch. Implement verified CORS preflight behavior in the final gateway configuration.

Deploying services/rules or running an EAS build requires the relevant authorization and environment configuration; this worktree does not auto-deploy. Schedule the deletion worker hourly with retries and deadline/failure monitoring. Test a synthetic deletion against the deployed environment before accepting the 30-day criterion. The new project's Firestore access must remain denied by default until reviewed rules are applied.

## iOS boundary

Google-only iOS is for internal/TestFlight distribution. `apps/student/eas.json` prepares internal profiles only. Apple developer provisioning, native OAuth clients, and an installed internal build remain necessary to verify #50. No public App Store submission is part of this MVP.
