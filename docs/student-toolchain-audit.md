# Student toolchain release gate (#61)

Reproduced from `npm ci --no-fund --no-audit` in the isolated short-path checkout on 2026-10-22, using the committed student lockfile, Node 24.11.1 and npm 11.6.2. The clean install added 646 packages; `npm audit --json` then reported 20 high affected dependency entries, zero critical/moderate/low entries. Raw audit and `npm explain braces node-forge --json` output are retained under ignored `tmp/verification/` in the issue-4 worktree, without credentials.

These are propagated dependency entries across two underlying advisories, not 20 unique vulnerabilities:

| Package | Underlying advisory | Affected range | Registry latest observed |
| --- | --- | --- | --- |
| braces | [GHSA-vfj7-8cjw-p6xm](https://github.com/advisories/GHSA-vfj7-8cjw-p6xm), nested-pattern stack exhaustion | <=3.0.3 | 3.0.3 |
| node-forge | [GHSA-86w9-cpqp-85rv](https://github.com/advisories/GHSA-86w9-cpqp-85rv), RSA signature validation | <=1.4.0 | 1.4.0 |

`npm view` still returns affected latest versions. npm's proposed Expo 44 downgrade is incompatible with the SDK 58/native stack and is not applied. Backend and isolated infrastructure audits being clear do not clear this student/build dependency tree.

The dependency-explanation output identifies Expo/CLI/Metro build-tool paths. A package's presence in the install does not prove execution in the browser/native application bundle. This checkpoint does not claim an absence of runtime exposure, harmless build/signing exposure, or an accepted risk. Build and signing pipelines remain within the release gate; local synthetic verification artifacts are not approved student releases.

Keep #61 open until a supported patched release or an explicitly evidenced inapplicability/mitigation clears every relevant high/critical finding. Then repeat clean-install audit, client checks, native/web builds, emulator authorization tests and the documented release decision. Do not suppress the audit or change its threshold to obtain completion.
