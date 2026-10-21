# Account infrastructure and rules verification

`environments/development.json` records public identifiers for the newly created development project. It contains no credentials. `gateway.yaml.template` prepares Firebase JWT verification and private backend invocation; it has not been deployed. Project creation, Identity Platform billing/OAuth setup, service IAM, secrets, gateway deployment and scheduled deletion remain separate verified steps under #18/#4.

Run the rules harness only against the demo emulator:

```powershell
npm ci --prefix infra
firebase emulators:exec --only firestore --project demo-casestudy-tech "npm --prefix infra test"
firebase emulators:exec --only firestore --project demo-casestudy-tech "uv run --project services/accounts --python 3.12 python -m pytest services/accounts/tests/test_store_emulator.py -q"
```

Java 21+ is required; verification used JDK 25. Do not replace the demo project ID with a live project to make a test pass. Test records are synthetic. The Python SDK uses anonymous emulator credentials; no production service credentials are needed.

The compatible Firebase 12/rules-testing 5 test line pins an old grpc-js 1.9.x dependency. The root harness override to grpc-js 1.14.6 resolves GHSA-m9gg-hp2v-232j and GHSA-f596-whhp-79r4 without downgrading Firebase or requiring the newer Node engine. All four rules tests pass after this same-major update and the harness audit reports zero vulnerabilities. Keep the rationale and regression checks when removing or changing the override.

The student's Expo/Metro toolchain still has separate unresolved findings tracked in #61; a clean infrastructure harness audit does not establish a clean application/build-tool audit.
