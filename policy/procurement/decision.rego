package aigc.procurement.decision

import rego.v1

default allow := false

local_simulation if {
  input.mode == "LOCAL_SIMULATION_ONLY"
  input.synthetic_data == true
  input.network_egress == false
  input.external_action == false
}

allow if local_simulation

valid_explicit_permit if {
  input.permit.authenticated == true
  input.permit.one_use == true
  input.permit.consumed == false
  input.permit.not_expired == true
  input.permit.operation_id == input.operation_id
  input.permit.destination == input.destination
  input.permit.payload_sha256 == input.payload_sha256
}

two_party_approval if {
  count(input.approvals) >= 2
  "legal" in input.approvals
  "procurement_manager" in input.approvals
}

allow if {
  input.action == "publish_contract"
  valid_explicit_permit
  two_party_approval
  input.contract.unsigned == false
  input.reconciliation_required == false
}

allow if {
  input.action == "send_payment"
  valid_explicit_permit
  two_party_approval
  input.payment.within_approved_ceiling == true
  input.payment.duplicate == false
  input.reconciliation_required == false
}

deny contains "external action lacks an exact authenticated one-use permit" if {
  input.external_action == true
  not valid_explicit_permit
}

deny contains "contract publication requires legal and procurement-manager approval" if {
  input.action == "publish_contract"
  not two_party_approval
}

deny contains "payment is outside the approved ceiling" if {
  input.action == "send_payment"
  input.payment.within_approved_ceiling != true
}

deny contains "duplicate or unreconciled payment is blocked" if {
  input.action == "send_payment"
  input.payment.duplicate == true
}

deny contains "indeterminate outcomes require reconciliation and prohibit automatic retry" if {
  input.reconciliation_required == true
}
