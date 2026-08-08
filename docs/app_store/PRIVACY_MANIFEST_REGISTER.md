# AIGC Privacy Manifest Register

Status: PRE-IMPLEMENTATION REGISTER

Apple requires valid privacy manifests for covered submissions and requires approved reasons for any required-reason APIs used by the app or third-party SDKs. This register must be regenerated from the shipping executable and dependency graph before submission.

Current repository audit of `main` found no native iOS/Xcode target or Swift source and therefore no implemented required-reason API usage to classify.

| API category | Source | Actual use | Approved reason required | Reason selected | Evidence | Status |
|---|---|---|---|---|---|---|
| File timestamp APIs | NOT_FOUND | Not implemented | If later used | none | No iOS source found | NOT_USED |
| System boot time APIs | NOT_FOUND | Not implemented | If later used | none | No iOS source found | NOT_USED |
| Disk-space APIs | NOT_FOUND | Not implemented | If later used | none | No iOS source found | NOT_USED |
| UserDefaults APIs | NOT_FOUND | Not implemented | If later used | none | No iOS source found | NOT_USED |

Rules:

- Never invent an approved-reason code.
- Any newly introduced SDK must be checked for its own privacy manifest and required-reason APIs.
- `PrivacyInfo.xcprivacy` becomes submission material only after the native target and linked dependencies are audited.
- Tracking and fingerprinting are prohibited by default.

Apple references:
- https://developer.apple.com/documentation/bundleresources/privacy-manifest-files
- https://developer.apple.com/documentation/bundleresources/describing-use-of-required-reason-api
