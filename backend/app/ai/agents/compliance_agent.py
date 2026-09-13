"""Compliance agent: carriers with expired/expiring insurance or
non-compliant status. Produces a block-list for assignment.
"""

from datetime import date, timedelta

from ... import models

NAME = "compliance_agent"


def run(db, org_id: str, expiring_within_days: int = 30) -> dict:
    carriers = (
        db.query(models.Carrier)
        .filter(models.Carrier.org_id == org_id,
                models.Carrier.is_active.is_(True))
        .all()
    )
    today = date.today()
    soon = today + timedelta(days=expiring_within_days)

    expired: list[dict] = []
    expiring: list[dict] = []
    non_compliant: list[dict] = []
    block_list: list[str] = []

    for c in carriers:
        entry = {"carrier_id": c.id, "carrier_name": c.legal_name,
                 "mc_number": c.mc_number,
                 "compliance_status": c.compliance_status,
                 "insurance_expiry": c.insurance_expiry.isoformat()
                 if c.insurance_expiry else None}
        blocked = False
        if c.insurance_expiry and c.insurance_expiry < today:
            expired.append(entry)
            blocked = True
        elif c.insurance_expiry and c.insurance_expiry <= soon:
            expiring.append(entry)
        if (c.compliance_status or "").lower() == "expired":
            non_compliant.append(entry)
            blocked = True
        if blocked:
            block_list.append(c.id)

    return {
        "recommendation": {
            "block_list": block_list,
            "blocked_count": len(block_list),
            "expired_insurance": expired,
            "expiring_soon": expiring,
            "non_compliant": non_compliant,
            "carriers_reviewed": len(carriers),
        },
        "reason": f"Reviewed {len(carriers)} active carriers: insurance "
                  f"expiry vs today, plus compliance_status.",
        "expected_impact": f"{len(block_list)} carrier(s) must be blocked "
                           "from new assignments until compliant.",
        "confidence": 0.95,
        "alternatives": [],
        "risks": [
            "Insurance data may be stale; verify with the carrier before blocking revenue.",
        ],
        "approval_required": False,  # read-only analysis; blocking is a human decision
    }
