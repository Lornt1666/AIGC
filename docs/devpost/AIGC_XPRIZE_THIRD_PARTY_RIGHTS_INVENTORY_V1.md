# AIGC XPRIZE Third-Party Rights Inventory V1

Status: `DIRECT DEPENDENCY LICENSES VERIFIED — TRANSITIVE / PROVIDER TERMS / IP CLOSEOUT PENDING`

## Purpose

Support the XPRIZE requirement that the Entrant be authorized to use third-party SDKs, APIs, data and integrations according to their terms.

This document is an engineering/compliance inventory, not legal certification.

## Exact competition runtime dependency surface

The dedicated Gemini vertical slice pins the following direct dependencies in `requirements-gemini.txt`:

```text
fastapi==0.140.0
uvicorn[standard]==0.51.0
pydantic==2.13.4
google-genai==1.75.0
google-cloud-storage==3.13.0
google-cloud-secret-manager==2.30.0
psycopg[binary]==3.3.4
psycopg-pool==3.3.1
```

The machine-readable direct-license inventory is:

```text
config/xprize_direct_dependency_licenses.json
```

and a regression requires that every non-comment direct requirement line has exactly one license record.

## Verified direct license families

```text
FastAPI                         MIT
Uvicorn                         BSD-3-Clause
Pydantic                        MIT
google-genai                    Apache-2.0
google-cloud-storage            Apache-2.0
google-cloud-secret-manager     Apache-2.0
psycopg + psycopg-binary        LGPL-3.0-only
psycopg-pool                    LGPL-3.0-only
```

Evidence sources are canonical upstream repositories and/or publisher-maintained PyPI metadata. The inventory intentionally records source type per dependency.

## Redistribution implications

### MIT

Preserve applicable copyright/license notices when redistributing substantial package portions.

### BSD-3-Clause

Preserve copyright, conditions and disclaimer and comply with the non-endorsement condition when redistributing.

### Apache-2.0

Preserve the Apache license and applicable notices/attribution requirements. Do not imply the license grants trademark rights beyond ordinary descriptive use.

### LGPL-3.0-only

Psycopg components require more careful distribution review than permissive dependencies. The current Project uses them as external Python packages rather than copying their implementation into AIGC source. If the final submission ZIP or distributed binary/container includes LGPL-covered binaries/libraries, the final notice/distribution process must preserve the LGPL/GPL notices and satisfy applicable combined-work/relinking requirements.

This inventory does not issue a legal conclusion on a specific distribution configuration.

## What is resolved

```text
direct pinned dependency enumeration = COMPLETE
direct dependency license family evidence = VERIFIED
unknown direct license = 0
requirements/license-map drift regression = PRESENT
```

## What remains unresolved

Direct dependency licensing is only one part of the XPRIZE rights condition.

Before final eligibility is marked complete, review:

```text
1. transitive dependency/SBOM license inventory;
2. final container/package redistribution notices;
3. Google Cloud / Gemini API terms applicable to the exact project/account/use;
4. any OpenAI use in judge/demo artifacts, if retained in the competition surface;
5. GitHub API/App terms for any repository integration exposed in the Project;
6. any third-party datasets, websites, customer content or scraped data;
7. logos, screenshots, videos, images, fonts or other media included in the final ZIP/video;
8. customer/user consent and rights for testimonials or evidence;
9. original-work/IP ownership declaration for AIGC competition-specific code and media.
```

## Eligibility state

The direct-package audit materially advances the `third_party_integration_rights` gate but does not close it:

```text
direct_dependency_licenses = EVIDENCED
transitive_dependency_licenses = UNRESOLVED
provider_terms = UNRESOLVED
third_party_content_rights = UNRESOLVED
original_work_and_ip_rights = UNVERIFIED
legal_certification = false
```

Therefore the parent submission contract remains:

```text
third_party_integration_rights = PARTIAL
```

until the final dependency/provider/content surface is fixed and reviewed.
