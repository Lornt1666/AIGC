from __future__ import annotations

from .production_connectors import ProductionConnectorBroker


class GovernedProductionConnectorBroker(ProductionConnectorBroker):
    """Compatibility name for the canonical governed connector broker.

    The complete fail-closed execution path now lives in ProductionConnectorBroker
    so direct and compatibility imports cannot diverge in policy, idempotency, or
    external-action evidence semantics.
    """
