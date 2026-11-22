# Verification: 019-provider-zdr-terms (#19)

This change is docs only, so there are no tests to run. The evidence is the record itself,
`docs/decisions/provider-zero-retention.md`, and `research.md`. These are the ACs as the owner split them on
2026-11-22. Getting confirmations and applying the settings moved to #115.

| AC | Status | Evidence |
|---|---|---|
| AC1. The terms status for each provider and model is recorded: published terms with the date read, the confirmation needed, and a verdict | **Met** | "Status by provider" has 9 rows. Each one has a published-terms column, a confirmation column and a verdict. All sources were read on 2026-11-22, with URLs in research.md. The written-terms rule says which confirmation each row needs. |
| AC2. The required settings are documented, with how to verify each one | **Met** | "Required settings" lists 1–12, each with its check: a `GET cacheConfig` call, a default to leave on, or a dated console screenshot. None is applied yet. Applying them is #115. |
| AC3. Any provider that can't meet RC-05 is rejected and not used | **Met, with a caveat** | Rejected: Frontier models, Model Garden partner models and batch STT. OpenAI is dropped by owner decision. Gemini-TTS is not to be used until it's confirmed. No code on `dev` calls any provider. The caveat: this holds only while #65 and #20 cite this record. |

Outcome: **complete** for the split scope.
