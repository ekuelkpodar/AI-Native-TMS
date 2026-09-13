"""AI control plane for the AI-Native TMS.

- providers.py: LLM provider abstraction (mock default, deterministic).
- registry.py: code-defined Agent Registry + Tool Registry (scope-checked).
- policy.py: policy engine (policies + autonomy gates + hard-deny list).
- approvals.py: propose/approve/reject actions through the policy engine.
- agents/: deterministic heuristic agents.
- routes.py: FastAPI router mounted at /api/v1/ai (see main.py).

Every AI action writes an ai_actions row and an audit_logs row.
"""

from . import approvals, policy, providers, registry  # noqa: F401

__all__ = ["approvals", "policy", "providers", "registry"]
