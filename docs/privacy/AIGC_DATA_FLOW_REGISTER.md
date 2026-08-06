# AIGC Data-Flow Register

Status: PRE-IMPLEMENTATION PRIVACY INVENTORY

No mobile data-collection claim is considered complete until the native iOS target and its dependencies exist and are inspected.

| Data class | Implemented collection | Planned collection | Purpose | Linked to identity | Tracking | On device | AIGC cloud | Google | Third party | Retention | Deletion | Consent | Apple category | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Account identifiers | REQUIRES_REVIEW | REQUIRES_REVIEW | TBD | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | REQUIRES_REVIEW | TBD | TBD | TBD | REQUIRES_REVIEW | TBD | No iOS implementation found on main |
| Email | REQUIRES_REVIEW | REQUIRES_REVIEW | TBD | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | REQUIRES_REVIEW | TBD | TBD | TBD | REQUIRES_REVIEW | Contact Info | No iOS implementation found on main |
| Name | REQUIRES_REVIEW | REQUIRES_REVIEW | TBD | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | REQUIRES_REVIEW | TBD | TBD | TBD | REQUIRES_REVIEW | Contact Info | No iOS implementation found on main |
| User-generated content | REQUIRES_REVIEW | true | Core AIGC workflow | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | REQUIRES_REVIEW | TBD | TBD | TBD | REQUIRES_REVIEW | User Content | Architecture only |
| Prompts | REQUIRES_REVIEW | true | Model execution | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | REQUIRES_REVIEW | Google Cloud / Vertex AI subject to final design | TBD | TBD | REQUIRES_REVIEW | User Content | Architecture only |
| Model outputs | REQUIRES_REVIEW | true | Present generated results | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | REQUIRES_REVIEW | Google subject to final design | TBD | TBD | REQUIRES_REVIEW | User Content | Architecture only |
| Diagnostics | REQUIRES_REVIEW | REQUIRES_REVIEW | Reliability | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | REQUIRES_REVIEW | TBD | TBD | TBD | REQUIRES_REVIEW | Diagnostics | No mobile SDK inventory yet |
| Crash data | REQUIRES_REVIEW | REQUIRES_REVIEW | Reliability | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | REQUIRES_REVIEW | TBD | TBD | TBD | REQUIRES_REVIEW | Diagnostics | No mobile SDK inventory yet |
| Performance data | REQUIRES_REVIEW | REQUIRES_REVIEW | Performance tuning | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | REQUIRES_REVIEW | TBD | TBD | TBD | REQUIRES_REVIEW | Diagnostics | No mobile SDK inventory yet |
| Usage analytics | REQUIRES_REVIEW | false | None by default | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | false | None by default | TBD | TBD | REQUIRES_REVIEW | Usage Data | Third-party analytics prohibited in M2 |
| Device identifiers | REQUIRES_REVIEW | REQUIRES_REVIEW | Security/attestation only if implemented | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | REQUIRES_REVIEW | Apple DeviceCheck/App Attest if implemented | TBD | TBD | REQUIRES_REVIEW | Identifiers | M3 only |
| Coarse location | NOT_FOUND | false | None | false | false | false | false | false | none | none | none | false | Location | No implementation found |
| Precise location | NOT_FOUND | false | None | false | false | false | false | false | none | none | none | false | Location | No implementation found |
| Contacts | NOT_FOUND | false | None | false | false | false | false | false | none | none | none | false | Contacts | No implementation found |
| Photos | NOT_FOUND | REQUIRES_REVIEW | TBD | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | REQUIRES_REVIEW | TBD | TBD | TBD | true if implemented | Photos or Videos | No implementation found |
| Audio | NOT_FOUND | REQUIRES_REVIEW | TBD | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | REQUIRES_REVIEW | TBD | TBD | TBD | true if implemented | Audio Data | No implementation found |
| Files | REQUIRES_REVIEW | REQUIRES_REVIEW | User-selected workflow input if implemented | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | REQUIRES_REVIEW | TBD | TBD | TBD | REQUIRES_REVIEW | User Content | No implementation found |
| Payment information | NOT_FOUND | false | None in current scope | false | false | false | false | false | none | none | none | false | Financial Info | No payment system found |
| Cloud evidence | NOT_FOUND | true | Governed execution receipts | REQUIRES_REVIEW | false | false | true | REQUIRES_REVIEW | Google Cloud planned | TBD | TBD | REQUIRES_REVIEW | Other Data | Cloud plan only |
| Support communications | REQUIRES_REVIEW | REQUIRES_REVIEW | User support | REQUIRES_REVIEW | false | REQUIRES_REVIEW | REQUIRES_REVIEW | false | TBD | TBD | TBD | REQUIRES_REVIEW | User Content | Support channel TBD |

Rules:

- `REQUIRES_REVIEW` is intentionally not equivalent to collected or not collected.
- Tracking defaults to false and must remain false unless a future feature deliberately changes that policy and passes a new privacy review.
- App Store privacy labels must be generated from the shipping build, linked SDK manifests, server behavior, and published privacy policy—not from this planning register alone.
