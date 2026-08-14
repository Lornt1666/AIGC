# AIGC Nexus Employment-OPS HYPERALPHA V1

## Status

This increment activates the requested Employment-OPS capability profile while preserving the existing Nexus constitutional boundary:

`Reasoning != Verification != Authority != Execution != Evidence`

Capability flags describe what the subsystem is designed to do. They do **not** manufacture empirical proof that an external ATS, telephony carrier, STT/TTS provider, or recruiter workflow is currently available. External activation remains evidence-gated.

## Activated capability profile

The canonical profile at `config/employment_ops.hyperalpha.json` requires:

- autonomous discovery, normalization, scam analysis, eligibility analysis, fit scoring, employer research;
- autonomous resume tailoring, cover-letter drafting, application-answer drafting, ATS navigation and safe-field prefill;
- automatic call answering, automatic speech to caller, autonomous interview dialogue, recruiter questioning and bounded negotiation;
- real-time STT/TTS capability targets;
- provider, ATS and telephony transport neutrality;
- continuous calibration/evolution;
- emergency stop and always-available human takeover.

It simultaneously fixes these invariants:

- self-authorization = false;
- model consensus, memory and evidence cannot become authority;
- unsupported candidate claims, identity misrepresentation and sensitive identity disclosure are prohibited;
- indeterminate automatic retry = false;
- read-only reconciliation is required.

## Authority integration

`src/core/nexus/employment_ops_policy.py` compiles Employment-OPS actions into the existing `ActionIntent` and `assess_autonomy(...)` path.

Non-consequential analysis/preparation stays autonomous. Submission and external communications are consequence-classified and require an existing bounded permit or a new explicit authority decision. No parallel `EmploymentPermit` or second governance type is introduced.

## Telephony

The following are enabled as target capabilities:

```text
AUTOMATIC_CALL_ANSWERING = TRUE
AUTOMATIC_SPEECH_TO_CALLER = TRUE
AUTOMATIC_NEGOTIATION = TRUE
REAL_TIME_STT = TRUE
REAL_TIME_TTS = TRUE
```

Operational activation is intentionally separate. `EmploymentOpsReadiness.operationally_active=true` is invalid until ATS transport, telephony transport, STT, TTS, consent/jurisdiction policy, emergency stop, application-submission canary, autonomous-call canary and autonomous-negotiation canary are all empirically verified.

This preserves truthful status reporting while keeping the capability target fully enabled.

## Negotiation

`NegotiationAuthorityEnvelope` defines bounded negotiation dimensions. It permits autonomous negotiation inside an approved envelope while hard-coding no autonomous binding offer acceptance, contract signing, government-ID disclosure, banking disclosure or legal attestation.

## Next implementation sequence

1. exact-head CI for this capability foundation;
2. candidate truth graph + application-state contracts;
3. deterministic opportunity/fit/scam engine;
4. provider-neutral ATS preparation adapter;
5. supported telephony transport discovery and adapter;
6. STT/TTS integration behind provider runtime;
7. emergency-stop and human-takeover integration test;
8. controlled external ATS submission canary;
9. controlled autonomous telephony canary;
10. controlled bounded negotiation canary.

No external call, recruiter communication, ATS submission, credential use, financial spend, or production activation is created by this increment alone.
