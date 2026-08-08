# AIGC App Store Completion Matrix

Canonical machine-readable ledger: `config/app_store/completion_ledger.json`.

| Gate | Current state | Completion evidence required |
|---|---|---|
| Apple Developer membership | NOT_STARTED | Account-side verification |
| App identifier / bundle identifier | NOT_STARTED | Apple registration receipt |
| Xcode project | NOT_STARTED | Repository implementation |
| Swift compilation | NOT_STARTED | Xcode 26+ build receipt |
| Privacy manifest | NOT_STARTED | Shipping-target audit and valid manifest |
| Required-reason APIs | NOT_STARTED | Executable/dependency audit plus approved reasons |
| Privacy labels | NOT_STARTED | App Store Connect data-practice record |
| Privacy policy | NOT_STARTED | Public policy URL and reviewed contents |
| Account deletion | NOT_STARTED | Required only if accounts exist; tested workflow |
| App Attest | NOT_STARTED | M3 implementation and test evidence |
| Entitlements/signing/archive | NOT_STARTED | Xcode/Apple receipts |
| TestFlight build | NOT_STARTED | App Store Connect receipt |
| Crash-free smoke | NOT_STARTED | TestFlight/device evidence |
| Screenshots/icon | NOT_STARTED | Assets derived from real candidate build |
| Metadata draft | IMPLEMENTED | This readiness branch only; unresolved fields remain TBD |
| Age rating/export compliance | NOT_STARTED | Current Apple questionnaire answers |
| Review notes/support/privacy URLs | NOT_STARTED | Final published resources |
| App Store Connect record | NOT_STARTED | Apple-side record |
| Submission authorization | BLOCKED | Exact signed build plus all preceding gates |

An `IMPLEMENTED` planning artifact is never equivalent to `APPLE_VALIDATED`.
