# Accounts environment setup

## Created development resources

- Google Cloud/Firebase project: `casestudy-tech-dev-2e03d0` (project number `613104664964`).
- Firebase web app: `1:613104664964:web:4d551431bea457c6baddd1`.
- Firebase Android app: `1:613104664964:android:20a4298bc75f3b35baddd1`; iOS app: `1:613104664964:ios:ca6ab7a9e5c7f984baddd1`. Both use `com.casestudytech.student` as package/bundle identifier.
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

The Identity Platform API key is restricted to Identity Toolkit/Secure Token APIs and provided to Cloud Run through Secret Manager. It was transferred in memory, without a plaintext env file or log. The student bundle receives only public client IDs and its HTTPS API address. No service-account JSON keys are needed. `infra/accounts/` defines separate account/worker custom roles, gateway invocation at the private service, scheduler invocation at the worker, secret-scoped runtime access, and build-repository/bucket access. Reviewed runtime project bindings contain the custom roles rather than Editor/Owner. Sensitive Terraform state lives in a separate private, versioned GCS bucket.

`infra/gateway.yaml.template` is rendered by Terraform for the deployed accounts gateway, `https://accounts-7tnmor5w.uc.gateway.dev`. Protected routes require Firebase JWTs. Explicit OPTIONS operations permit preflight without a student JWT, while the backend restricts origins to this project's Firebase hosting domains. The backend independently verifies the original forwarded token and deletion state; IAM prevents direct unauthenticated Cloud Run invocation. Six live gateway health/auth/CORS checks passed, both cleanup alert policies were created after metric propagation, and the final full Terraform plan reports no changes. Public exchange/refresh abuse controls and verified alert notification destinations remain launch gates.

The private accounts service, separate deletion job, hourly UTC scheduler and tested Firestore rules are deployed in this development project. Live synthetic worker verification removed one queued account and its scores before its original deadline, retained a denial marker and preserved the other synthetic owner. The actual scheduler also dispatched a successful execution. These checks do not prove real Google sign-in or deletion through the student UI. See [the infrastructure runbook](../infra/accounts/README.md) and [Mac verification handoff](ios-mac-handoff.md). No student client release, session/grading service deployment or production promotion is claimed.

## iOS boundary

Google-only iOS is for internal/TestFlight distribution. `apps/student/eas.json` prepares internal profiles only. Sandy owns all Apple development on Mac; follow [the Mac handoff](ios-mac-handoff.md). Apple developer provisioning, native OAuth clients, and an installed internal build remain necessary to verify #50. No public App Store submission is part of this MVP.
