# Owner approval gate (#72)
Branch: feature/72-access-approval-gate · Lead run: 2026-11-24 · Status: verifying
Intent: an account reaches no protected data until access/{uid} is approved; idempotent one-time access request; guard and Firestore rules fail closed; deletion erases the access record; no name or email in logs.
Change surfaces: accounts service guard and routes, domain types, Firestore store, firestore.rules, gateway config, deletion cleanup.
Likely touch points: services/accounts/cst_accounts/{domain,api,store,deletion,firebase}.py, services/accounts/tests/, infra/firestore.rules, infra/rules.test.mjs, infra/gateway.yaml.template, infra/accounts/check_gateway.py, READMEs.
Coordination: #73/#74/#75 build on the access record; #31 must adopt the guard. 004 and 019 plans are stale (not active).
