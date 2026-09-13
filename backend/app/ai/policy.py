"""Policy engine.

PolicyEngine.evaluate(db, org_id, action, context) -> decision dict.

action:  {agent, action_type, entity_type, entity_id, payload}
context: {user, autonomy_level (0-4), risk_level (low|medium|high)}

Decision: allow | require_approval | deny | notify (+ matched policy, reason).

Evaluation order:
  1. Hard-deny list (never auto): cross-tenant access, financial record
     mutation/deletion without approval, secret/config exposure. These can
     only ever resolve to require_approval (or deny when a policy says deny).
  2. Org policies ordered by priority (ascending — lower number wins);
     first policy whose conditions all match decides.
  3. Autonomy gates when no policy matches:
       L0 observe-only  -> mutations denied, reads allowed
       L1 recommend-only -> mutations need approval
       L2 approval-gated -> mutations need approval
       L3 low-risk auto  -> auto only when risk is low, else approval
       L4 auto within policy -> auto (hard-deny list still applies)

Conditions are {field, op, value} evaluated against the action via dotted
paths (payload.* supported). Ops: ==, !=, >, >=, <, <=, in, contains.
"""

from .. import models
from .registry import READ_ACTIONS

# Entity types whose mutation is "financial" for the hard-deny list.
_FINANCIAL_ENTITIES = {"invoices", "payments"}
# Entity types whose mutation would expose secrets / config.
_SENSITIVE_ENTITIES = {"integrations", "settings", "feature_flags", "users",
                       "roles", "organizations"}

_VALID_EFFECTS = {"allow", "require_approval", "deny", "notify"}


def _resolve(path: str, scope: dict):
    """Resolve a dotted path against the evaluation scope."""
    current: object = scope
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            return None
    return current


def _compare(field_value, op: str, expected) -> bool:
    try:
        if op == "==":
            return field_value == expected
        if op == "!=":
            return field_value != expected
        if op == ">":
            return field_value is not None and field_value > expected
        if op == ">=":
            return field_value is not None and field_value >= expected
        if op == "<":
            return field_value is not None and field_value < expected
        if op == "<=":
            return field_value is not None and field_value <= expected
        if op == "in":
            return field_value in (expected or [])
        if op == "contains":
            if field_value is None:
                return False
            if isinstance(field_value, (list, tuple, set)):
                return expected in field_value
            return str(expected) in str(field_value)
    except TypeError:
        return False
    return False


def _conditions_match(conditions: list, scope: dict) -> bool:
    for cond in conditions or []:
        field = cond.get("field", "")
        op = cond.get("op", "==")
        expected = cond.get("value")
        if not _compare(_resolve(field, scope), op, expected):
            return False
    return True


def _hard_deny_kind(action: dict, org_id: str) -> str | None:
    """Return a hard-deny reason key, or None when the action is not hard-deny."""
    payload = action.get("payload") or {}
    action_type = action.get("action_type") or ""
    entity_type = (action.get("entity_type") or "").lower()
    is_mutation = action_type not in READ_ACTIONS

    # Cross-tenant data access: payload names a different org.
    payload_org = payload.get("org_id")
    if payload_org and payload_org != org_id:
        return "cross_tenant"

    # Secret / config exposure.
    if entity_type in _SENSITIVE_ENTITIES and is_mutation:
        return "sensitive_config"
    lowered = action_type.lower()
    if "secret" in lowered or "config" in lowered or "api_key" in lowered:
        return "sensitive_config"

    # Deletions always need a human.
    if lowered.startswith("delete_") or payload.get("delete") is True:
        return "deletion"

    # Financial record mutation without approval.
    if entity_type in _FINANCIAL_ENTITIES and is_mutation:
        return "financial_mutation"
    return None


class PolicyEngine:
    @staticmethod
    def evaluate(db, org_id: str, action: dict, context: dict) -> dict:
        action_type = action.get("action_type") or ""
        payload = dict(action.get("payload") or {})
        autonomy = int(context.get("autonomy_level", 1))
        risk = (context.get("risk_level") or "medium").lower()
        is_mutation = action_type not in READ_ACTIONS

        scope = {
            "agent": action.get("agent"),
            "action_type": action_type,
            "entity_type": action.get("entity_type"),
            "entity_id": action.get("entity_id"),
            "payload": payload,
            "risk_level": risk,
            "autonomy_level": autonomy,
        }

        policies = (
            db.query(models.Policy)
            .filter(models.Policy.org_id == org_id,
                    models.Policy.is_active.is_(True))
            .order_by(models.Policy.priority.asc())
            .all()
        )

        hard_kind = _hard_deny_kind(action, org_id)
        if hard_kind:
            # A matching policy may still force a deny; otherwise the
            # hard-deny list resolves to require_approval (never auto).
            for policy in policies:
                rule = policy.rule or {}
                if rule.get("effect") == "deny" and _conditions_match(
                        rule.get("conditions"), scope):
                    return {
                        "decision": "deny",
                        "policy": _policy_dict(policy),
                        "reason": f"Hard-deny ({hard_kind}) and policy "
                                  f"'{policy.name}' denies it.",
                    }
            return {
                "decision": "require_approval",
                "policy": None,
                "reason": f"Hard-deny list ({hard_kind}): never auto-approved.",
            }

        def _autonomy_gate(matched_policy: dict | None, policy_name: str | None):
            """Apply autonomy gates after a policy allowed the action."""
            if not is_mutation:
                return {"decision": "allow", "policy": matched_policy,
                        "reason": f"Read-only action; policy "
                                  f"'{policy_name}' allows it." if policy_name
                                  else "Read-only action; no policy matched."}
            if autonomy <= 1:
                return {"decision": "require_approval", "policy": matched_policy,
                        "reason": f"Autonomy L{autonomy} is recommend-only; "
                                  f"mutations need approval."}
            if autonomy == 2:
                return {"decision": "require_approval", "policy": matched_policy,
                        "reason": "Autonomy L2 is approval-gated; "
                                  "mutations need approval."}
            if autonomy == 3:
                if risk == "low":
                    return {"decision": "allow", "policy": matched_policy,
                            "reason": "Autonomy L3 with low risk: auto-approved."}
                return {"decision": "require_approval", "policy": matched_policy,
                        "reason": f"Autonomy L3 requires low risk (risk={risk}); "
                                  "needs approval."}
            return {"decision": "allow", "policy": matched_policy,
                    "reason": "Autonomy L4: auto within policy."}

        for policy in policies:
            rule = policy.rule or {}
            effect = rule.get("effect")
            if effect not in _VALID_EFFECTS:
                continue
            if not _conditions_match(rule.get("conditions"), scope):
                continue
            matched = _policy_dict(policy)
            if effect == "deny":
                return {"decision": "deny", "policy": matched,
                        "reason": f"Policy '{policy.name}' denies this action."}
            if effect == "require_approval":
                return {"decision": "require_approval", "policy": matched,
                        "reason": f"Policy '{policy.name}' requires approval.",
                        "required_role": rule.get("required_role", "dispatcher")}
            if effect == "notify":
                return {"decision": "notify", "policy": matched,
                        "reason": f"Policy '{policy.name}' allows with notification."}
            # effect == "allow": still subject to autonomy gates for mutations
            return _autonomy_gate(matched, policy.name)

        return _autonomy_gate(None, None)


def _policy_dict(policy: models.Policy) -> dict:
    return {"id": policy.id, "name": policy.name,
            "priority": policy.priority, "rule": policy.rule or {}}
