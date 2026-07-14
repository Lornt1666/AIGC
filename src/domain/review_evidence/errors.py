class ReviewEvidenceError(ValueError):
    """Base error for review-evidence and human-judgment failures."""


class ReviewEvidenceConflict(ReviewEvidenceError):
    """Raised when immutable review evidence is replayed with different content."""


class ReviewEvidenceNotFound(ReviewEvidenceError):
    """Raised when a required packet or judgment receipt cannot be resolved."""


class ReviewJudgmentDenied(ReviewEvidenceError):
    """Raised when a requested human judgment is not permitted by packet evidence."""
