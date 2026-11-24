# Tasks: Owner approval gate (#72)

Status: done

- [x] T1 @implementer: domain model (FR-1). `AccessState`, `Profile` (name and email hidden from repr), `ProfileUnusable`, and the `AccessNotApproved` and `AccessDenied` exceptions.
- [x] T2 @implementer: `FirebaseIdentity.profile` (FR-3, D3). Verified email required; name NFC-normalized with controls and invisible format characters stripped; 403 `profile_unusable`.
- [x] T3 @implementer: `FirestoreAccounts.access_state` / `request_access` (FR-3, FR-4, FR-6). Create-once transaction that re-reads the deletion marker; AlreadyExists is re-read; a malformed record fails closed; retry exhaustion gives 503.
- [x] T4 @implementer: API (FR-2, FR-3, FR-5). `GET /v1/access` and `POST /v1/access/request`; the `approved` guard on `/v1/scores` and `/v1/me` (owner T5).
- [x] T5 @implementer: deletion cleanup removes `access/{uid}` (FR-8). `erase_scores` is renamed `erase_student_data`.
- [x] T6 @implementer: Firestore rules (FR-7). `approved(uid)` inside `activeOwner`; explicit server-only `access/{uid}`.
- [x] T7 @devops: gateway routes and preflights, plus smoke probes (FR-11).
- [x] T8 @implementer: tests for AC1–AC7, the route inventory, the threat-model extras, and the rules matrix. A mutation check showed the rules tests catch a missing approval rule.
- [x] T9 docs: services/accounts/README.md, ARCHITECTURE component row, POLICY §10 accepted risk (owner T4).
- [x] T10 @qa: independent AC evidence in verification.md, plus a transcript demo GIF.
- [x] T11 review: security audit, policy review, review.md.
