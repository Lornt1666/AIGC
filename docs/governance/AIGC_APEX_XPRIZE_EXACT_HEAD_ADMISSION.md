# APEX × XPRIZE Exact-Head Admission Marker

The prior AIGC CI #2906 attempts failed before producing validation steps or an artifact. They therefore do not establish a repository defect and do not establish a passing admission.

This commit creates a new immutable candidate head and requires a completely new pull-request-triggered AIGC CI receipt.

Required:

```text
requested_head_sha == observed_head_sha
shared canonical validation == PASS
APEX completion regressions == PASS
authorization reconstruction regressions == PASS
XPRIZE submission-contract regressions == PASS
retained exact-head artifact == PRESENT
```

No merge, cloud, financial, Devpost-update, submission, or production authority is granted.
