from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping, Protocol

from src.domain.identity import IdentityProviderClass, ProviderVerification


class IdentityProviderProtocol(Protocol):
    provider_class: IdentityProviderClass
    provider_binding_id: str

    def verify(
        self,
        raw_assertion: Mapping[str, Any],
        *,
        now: datetime,
    ) -> ProviderVerification:
        """Verify untrusted provider input and return only redacted evidence."""
