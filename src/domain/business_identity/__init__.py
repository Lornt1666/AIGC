"""Business identity, tenancy, and profile contracts.

This package is subordinate to ``src.domain.identity``. It describes business
metadata and never grants authentication, membership, session, role, scope,
connector, production, or external-action authority.
"""
from .contracts import (
    BusinessEntityClassification,
    BusinessIdentityAuthorizationError,
    BusinessIdentityConflict,
    BusinessIdentityContractError,
    BusinessIdentityError,
    BusinessIdentityNotFound,
    BusinessIdentityReplayConflict,
    BusinessIdentityRegistryRepository,
    BusinessProfile,
    BusinessProfileLifecycleState,
    DataResidencyClassification,
    EvidenceClassification,
    EvidencePurpose,
    EvidenceReference,
    TenantLifecycleState,
    TenantRecord,
    TenantType,
    business_profile_lifecycle_states,
    canonical_digest,
    canonical_json,
    tenant_lifecycle_states,
)

__all__ = [
    "BusinessEntityClassification",
    "BusinessIdentityAuthorizationError",
    "BusinessIdentityConflict",
    "BusinessIdentityContractError",
    "BusinessIdentityError",
    "BusinessIdentityNotFound",
    "BusinessIdentityReplayConflict",
    "BusinessIdentityRegistryRepository",
    "BusinessProfile",
    "BusinessProfileLifecycleState",
    "DataResidencyClassification",
    "EvidenceClassification",
    "EvidencePurpose",
    "EvidenceReference",
    "TenantLifecycleState",
    "TenantRecord",
    "TenantType",
    "business_profile_lifecycle_states",
    "canonical_digest",
    "canonical_json",
    "tenant_lifecycle_states",
]
