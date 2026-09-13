"""Deterministic heuristic agents.

Every agent exposes run(db, org_id, **params) -> dict with keys:
  recommendation, reason, expected_impact, confidence (0-1),
  alternatives[], risks[], approval_required (bool).
No network calls, no randomness.
"""

from . import (  # noqa: F401
    carrier_agent,
    compliance_agent,
    customer_service_agent,
    dispatch_agent,
    exception_agent,
    finance_agent,
    ops_analyst_agent,
    pricing_agent,
    routing_agent,
)

AGENT_RUNNERS = {
    "dispatch_agent": dispatch_agent.run,
    "routing_agent": routing_agent.run,
    "carrier_agent": carrier_agent.run,
    "customer_service_agent": customer_service_agent.run,
    "exception_agent": exception_agent.run,
    "pricing_agent": pricing_agent.run,
    "finance_agent": finance_agent.run,
    "compliance_agent": compliance_agent.run,
    "ops_analyst_agent": ops_analyst_agent.run,
}

__all__ = ["AGENT_RUNNERS"]
