# Terraform Inert Evidence Contract

This module produces provider-free, no-resource Terraform output for evidence review.

It contains:

- variables;
- locals;
- `check` blocks;
- outputs.

It contains no:

- `resource` blocks;
- `data` blocks;
- provider configuration;
- credentials;
- Secret Manager values;
- network calls;
- Terraform apply command;
- external action.

The contract requires:

```text
repository_clean = true
provider_lock_present = true
resource_change_count = 0
hosted_ci_replacement = false
operator_review_required = true
provider_action_performed = false
terraform_apply_performed = false
external_action_performed = false
```

A successful plan validates only that the supplied evidence assertions are internally consistent. It is not operational Google Cloud evidence, authority to merge, authority to apply Terraform, or a substitute for GitHub-hosted CI.
