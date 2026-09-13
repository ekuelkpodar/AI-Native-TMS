"""LLM provider abstraction.

- AIProvider: base class with complete(prompt, **kwargs).
- MockProvider: default, fully deterministic, no network. Also hosts the
  deterministic keyword-intent parser used by POST /ai/command and a
  deterministic draft-text generator used by the customer service agent.
- OpenAIProvider / AnthropicProvider: stubs. They raise ProviderNotConfigured
  unless OPENAI_API_KEY / ANTHROPIC_API_KEY are set, and they never perform
  real network calls in this build (deterministic-only rule).

Every completion is logged to the ai_usage table when db + org_id are passed.
"""

import json
import os
import re
from datetime import datetime, timezone

from .. import models
from ..config import settings

# Pricing used only to estimate mock usage cost (USD per token).
_MOCK_INPUT_PER_TOKEN = 0.5 / 1_000_000
_MOCK_OUTPUT_PER_TOKEN = 1.5 / 1_000_000


class ProviderNotConfigured(Exception):
    """Raised when a provider cannot be used (missing API key, etc.)."""


class AIProvider:
    """Base provider. complete() returns a dict with at least {"text": str}."""

    name = "base"
    model = "unknown"

    def complete(self, prompt: str, **kwargs) -> dict:
        raise NotImplementedError


def _estimate_tokens(text: str) -> int:
    return max(1, len(text or "") // 4)


def _log_usage(db, *, org_id: str, agent_name: str, model: str,
               prompt: str, text: str, task_type: str | None) -> None:
    tokens_in = _estimate_tokens(prompt)
    tokens_out = _estimate_tokens(text)
    cost = tokens_in * _MOCK_INPUT_PER_TOKEN + tokens_out * _MOCK_OUTPUT_PER_TOKEN
    db.add(models.AIUsage(
        org_id=org_id,
        agent_name=agent_name,
        model=model,
        tokens_in=tokens_in,
        tokens_out=tokens_out,
        est_cost_usd=round(cost, 6),
        task_type=task_type,
    ))
    db.flush()


class MockProvider(AIProvider):
    """Deterministic mock provider. No network, no randomness."""

    name = "mock"
    model = "mock-1"

    def complete(self, prompt: str, **kwargs) -> dict:
        db = kwargs.get("db")
        org_id = kwargs.get("org_id")
        agent_name = kwargs.get("agent_name") or "ai"
        task_type = kwargs.get("task_type")

        if prompt.startswith("PARSE_INTENT:"):
            message = prompt[len("PARSE_INTENT:"):].strip()
            intent, entities = self._parse_intent(message)
            text = json.dumps({"intent": intent, "entities": entities})
            result = {"text": text, "intent": intent, "entities": entities}
        elif prompt.startswith("DRAFT:"):
            facts = json.loads(prompt[len("DRAFT:"):].strip() or "{}")
            text = self._draft_email(facts)
            result = {"text": text}
        else:
            text = f"[mock] Deterministic completion for prompt: {prompt[:200]}"
            result = {"text": text}

        if db is not None and org_id:
            _log_usage(db, org_id=org_id, agent_name=agent_name,
                       model=self.model, prompt=prompt, text=text,
                       task_type=task_type)
        return result

    # ------------------------------------------------------------------
    # Deterministic keyword-intent parser (used by POST /ai/command)
    # ------------------------------------------------------------------

    _INTENT_RULES = [
        ("delayed_loads", ["delay", "late", "behind schedule", "running late"]),
        ("unassigned_loads", ["unassigned", "not assigned", "need driver",
                              "dispatch board", "dispatch"]),
        ("match_carriers", ["match carrier", "find carrier", "best carrier",
                            "rank carrier", "carrier for"]),
        ("optimize_route", ["optimiz", "re-route", "reroute", "shortest route"]),
        ("exceptions", ["exception"]),
        ("finance", ["invoice", "payment", "billing", "finance", "overdue",
                     "receivable"]),
        ("compliance", ["complian", "insurance", "authority", "safety"]),
        ("forecast", ["forecast", "predict", "projection"]),
        ("pricing", ["price", "pricing", "quote", "margin", "rate for"]),
        ("analytics", ["kpi", "analytic", "dashboard", "performance", "report"]),
        ("load_status", ["status of", "where is", "track ", "tracking"]),
        ("route", ["route"]),  # bare "route" falls through to optimize_route
    ]

    def _parse_intent(self, message: str) -> tuple[str, dict]:
        msg = message.lower()
        entities: dict = {}

        m = re.search(r"\bLD-(\d+)\b", message, re.IGNORECASE)
        if m:
            entities["load_number"] = f"LD-{m.group(1)}"
        m = re.search(r"top\s*(\d+)", msg)
        if m:
            entities["top_n"] = int(m.group(1))
        else:
            m = re.search(r"(\d+)\s+carriers?", msg)
            if m:
                entities["top_n"] = int(m.group(1))
        for ftype in ("volume", "capacity", "cost", "lane_pricing", "driver_demand"):
            if ftype in msg:
                entities["forecast_type"] = ftype
                break
        m = re.search(r"(\d+)\s*(month|period|week)", msg)
        if m:
            entities["periods"] = int(m.group(1))

        for intent, keywords in self._INTENT_RULES:
            if any(k in msg for k in keywords):
                if intent == "route":
                    intent = "optimize_route"
                if intent in ("match_carriers", "optimize_route", "load_status") \
                        and "load_number" not in entities:
                    # These intents need a load reference; without one, fall
                    # through to help instead of guessing.
                    continue
                return intent, entities
        return "help", entities

    # ------------------------------------------------------------------
    # Deterministic draft generator (used by the customer service agent)
    # ------------------------------------------------------------------

    def _draft_email(self, facts: dict) -> str:
        load_number = facts.get("load_number", "N/A")
        customer = facts.get("customer_name", "valued customer")
        status = facts.get("status", "in transit")
        origin = facts.get("origin", "")
        destination = facts.get("destination", "")
        eta = facts.get("eta") or "to be confirmed"
        delay = facts.get("delay_explanation") or ""
        body_lines = [
            f"Subject: Shipment update for load {load_number}",
            "",
            f"Dear {customer},",
            "",
            f"This is an update on your shipment {load_number} "
            f"({origin} -> {destination}).",
            f"Current status: {status}.",
            f"Estimated delivery: {eta}.",
        ]
        if delay:
            body_lines += ["", f"Delay details: {delay}"]
        body_lines += [
            "",
            "We are monitoring this shipment and will notify you of any "
            "further changes. Reply to this message with any questions.",
            "",
            "Best regards,",
            "Customer Service",
        ]
        return "\n".join(body_lines)


class OpenAIProvider(AIProvider):
    """Stub. Raises ProviderNotConfigured unless OPENAI_API_KEY is set.

    Even with a key, this build never performs real network calls
    (deterministic-only rule); it raises instead of calling the API.
    """

    name = "openai"
    model = "gpt-4o-mini"

    def __init__(self) -> None:
        self.api_key = os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ProviderNotConfigured(
                "OPENAI_API_KEY is not set. Set it or use AI_PROVIDER=mock."
            )

    def complete(self, prompt: str, **kwargs) -> dict:
        if not self.api_key:
            raise ProviderNotConfigured("OPENAI_API_KEY is not set.")
        raise RuntimeError(
            "External LLM calls are disabled in this deterministic build. "
            "Use AI_PROVIDER=mock."
        )


class AnthropicProvider(AIProvider):
    """Stub. Raises ProviderNotConfigured unless ANTHROPIC_API_KEY is set.

    Even with a key, this build never performs real network calls
    (deterministic-only rule); it raises instead of calling the API.
    """

    name = "anthropic"
    model = "claude-3-5-haiku"

    def __init__(self) -> None:
        self.api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ProviderNotConfigured(
                "ANTHROPIC_API_KEY is not set. Set it or use AI_PROVIDER=mock."
            )

    def complete(self, prompt: str, **kwargs) -> dict:
        if not self.api_key:
            raise ProviderNotConfigured("ANTHROPIC_API_KEY is not set.")
        raise RuntimeError(
            "External LLM calls are disabled in this deterministic build. "
            "Use AI_PROVIDER=mock."
        )


def get_provider() -> AIProvider:
    """Select the provider via the AI_PROVIDER env var (default "mock")."""
    name = (os.environ.get("AI_PROVIDER") or settings.AI_PROVIDER or "mock").lower()
    if name == "openai":
        return OpenAIProvider()
    if name == "anthropic":
        return AnthropicProvider()
    return MockProvider()


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)
