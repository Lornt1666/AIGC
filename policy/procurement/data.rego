package aigc.procurement.data

import rego.v1

default allow_store := false
default allow_export := false

allow_store if {
  input.classification == "SYNTHETIC"
  input.contains_raw_pii == false
}

allow_store if {
  input.contains_raw_pii == false
  input.redaction_verified == true
  input.region in input.allowed_regions
  input.retention_days <= input.maximum_retention_days
}

allow_export if {
  allow_store
  input.export_authorized == true
  input.destination_allowlisted == true
  input.payload_sha256 != ""
}

deny contains "raw PII cannot be stored" if input.contains_raw_pii == true
deny contains "redaction evidence is missing" if {
  input.classification != "SYNTHETIC"
  input.redaction_verified != true
}
deny contains "data residency is not allowed" if not input.region in input.allowed_regions
deny contains "export lacks explicit destination-bound authority" if {
  input.export_requested == true
  not allow_export
}
