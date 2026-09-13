"""Finance agent: invoice hygiene — missing documents, duplicate line items,
overdue invoices — with reconciliation suggestions.
"""

from datetime import date

from ... import models

NAME = "finance_agent"


def _load_docs(db, org_id: str, load_id: str) -> set[str]:
    rows = (
        db.query(models.Document.doc_type)
        .filter(models.Document.org_id == org_id,
                models.Document.entity_type == "loads",
                models.Document.entity_id == load_id)
        .all()
    )
    return {r[0] for r in rows}


def run(db, org_id: str) -> dict:
    invoices = (
        db.query(models.Invoice)
        .filter(models.Invoice.org_id == org_id,
                models.Invoice.status != "void")
        .order_by(models.Invoice.due_date.asc().nullslast())
        .all()
    )
    today = date.today()
    findings: list[dict] = []
    suggestions: list[str] = []

    for inv in invoices:
        # Duplicate line items: same (description, amount) twice or more.
        seen: dict[tuple, int] = {}
        for line in inv.line_items or []:
            key = (str(line.get("description", "")).strip().lower(),
                   round(float(line.get("amount", 0) or 0), 2))
            seen[key] = seen.get(key, 0) + 1
        dupes = [k for k, n in seen.items() if n > 1]
        if dupes:
            findings.append({
                "type": "duplicate_line_items",
                "invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "duplicates": [{"description": d, "amount": a} for d, a in dupes],
            })
            suggestions.append(
                f"Invoice {inv.invoice_number}: review and remove duplicate "
                f"line items before issuing.")

        # Missing documents on the invoiced load.
        if inv.load_id:
            docs = _load_docs(db, org_id, inv.load_id)
            missing = [d for d in ("pod", "bol") if d not in docs]
            if missing:
                findings.append({
                    "type": "missing_docs",
                    "invoice_id": inv.id,
                    "invoice_number": inv.invoice_number,
                    "load_id": inv.load_id,
                    "missing": missing,
                })
                suggestions.append(
                    f"Invoice {inv.invoice_number}: collect missing "
                    f"{', '.join(missing).upper()} before collecting payment.")

        # Overdue.
        if inv.due_date and inv.due_date < today and inv.status != "paid":
            outstanding = round(float(inv.total or 0) - float(inv.amount_paid or 0), 2)
            findings.append({
                "type": "overdue",
                "invoice_id": inv.id,
                "invoice_number": inv.invoice_number,
                "due_date": inv.due_date.isoformat(),
                "outstanding_usd": outstanding,
            })
            suggestions.append(
                f"Invoice {inv.invoice_number}: ${outstanding} overdue since "
                f"{inv.due_date.isoformat()} — send a payment reminder.")

    return {
        "recommendation": {
            "findings": findings,
            "findings_count": len(findings),
            "invoices_reviewed": len(invoices),
            "suggestions": suggestions,
        },
        "reason": f"Checked {len(invoices)} invoices for duplicate lines, "
                  f"missing load documents, and overdue balances.",
        "expected_impact": f"{len(findings)} issue(s) flagged; cleaning them "
                           "up shortens the cash-conversion cycle.",
        "confidence": 0.85,
        "alternatives": [],
        "risks": [
            "Findings are heuristic; a human should confirm before voiding or reissuing.",
        ],
        "approval_required": True,  # financial actions need a human
    }
