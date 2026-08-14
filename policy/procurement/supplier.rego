package aigc.procurement.supplier

import rego.v1

default allow_onboarding := false

allow_onboarding if {
  input.kyc.status == "PASS"
  input.sanctions_match == false
  input.identity_verified == true
  input.risk_score <= input.policy.risk_score_threshold
  input.manual_review_complete == true
}

deny contains "KYC is not complete" if input.kyc.status != "PASS"
deny contains "sanctions match blocks onboarding" if input.sanctions_match == true
deny contains "supplier identity is unverified" if input.identity_verified != true
deny contains "supplier risk exceeds policy threshold" if input.risk_score > input.policy.risk_score_threshold
deny contains "manual compliance review is required" if input.manual_review_complete != true
