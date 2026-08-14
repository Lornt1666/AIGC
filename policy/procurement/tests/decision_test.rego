package aigc.procurement.decision_test

import rego.v1
import data.aigc.procurement.decision

test_local_synthetic_simulation_is_allowed if {
  decision.allow with input as {"mode":"LOCAL_SIMULATION_ONLY","synthetic_data":true,"network_egress":false,"external_action":false}
}

test_unpermitted_payment_is_denied if {
  not decision.allow with input as {"action":"send_payment","external_action":true,"operation_id":"op","destination":"bank","payload_sha256":"abc","permit":{},"approvals":[],"payment":{"within_approved_ceiling":true,"duplicate":false},"reconciliation_required":false}
}

test_duplicate_payment_is_denied if {
  some reason in decision.deny with input as {"action":"send_payment","external_action":true,"operation_id":"op","destination":"bank","payload_sha256":"abc","permit":{"authenticated":true,"one_use":true,"consumed":false,"not_expired":true,"operation_id":"op","destination":"bank","payload_sha256":"abc"},"approvals":["legal","procurement_manager"],"payment":{"within_approved_ceiling":true,"duplicate":true},"reconciliation_required":false}
  reason == "duplicate or unreconciled payment is blocked"
}
