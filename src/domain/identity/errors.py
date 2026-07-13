class IdentityBoundaryError(ValueError):
    """Base error for PIBC-v1 contract and boundary failures."""


class IdentityContractError(IdentityBoundaryError):
    """Raised when a normalized context or receipt violates its schema."""


class IdentityReplayConflict(IdentityBoundaryError):
    """Raised when one provider assertion is reused with different intent."""
