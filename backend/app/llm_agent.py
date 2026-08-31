from __future__ import annotations

import json
import os
from dataclasses import asdict
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from .investigator import CandidateAction, Diagnosis, DeterministicInvestigator
from .models import Incident, TransactionState
from .tools import InvestigationTools
from .guardrails import sanitize_diagnosis


class EvidenceClaim(BaseModel):
    fact: str
    value: Any
    source: str
    confidence: float = Field(ge=0.0, le=1.0)


class AIAction(BaseModel):
    action_type: str
    reason: str
    expected_recovery: int = Field(ge=0)
    expected_cost: int = Field(ge=0)
    confidence: float = Field(ge=0.0, le=1.0)


class DiagnosisOutput(BaseModel):
    incident_type: str
    root_cause: str
    confidence: float = Field(ge=0.0, le=1.0)
    summary: str
    evidence: List[EvidenceClaim]
    candidate_actions: List[AIAction]
    recommended_action: str


SYSTEM_PROMPT = """
You are PAYGUARD, a financial incident investigation agent.

Your job is to investigate transaction incidents using ONLY verified evidence exposed by tools.
You are NOT allowed to invent payment status, order status, inventory, fulfillment state, amounts, or events.
You may infer a root cause, but clearly distinguish inference from observed evidence.

Rules:
1. Payment/order state from authoritative projected state is evidence; do not override it with guesses.
2. Prefer the smallest safe recovery action that preserves merchant revenue.
3. Refunds are never automatically executable in this MVP.
4. Never claim an action was executed; you only diagnose and recommend.
5. If evidence is insufficient or contradictory, recommend ESCALATE_HUMAN.
6. Every diagnosis must cite concrete evidence.
7. Candidate action amounts must come from the transaction evidence, not invention.
8. Output concise, structured, operational reasoning.
""".strip()


def _tool_specs() -> List[Dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": "get_payment",
            "description": "Get projected payment state and identifiers for the transaction.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "type": "function",
            "name": "get_order",
            "description": "Get projected order state and identifiers for the transaction.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "type": "function",
            "name": "get_inventory",
            "description": "Get projected inventory availability for the transaction.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "type": "function",
            "name": "get_fulfillment",
            "description": "Get projected fulfillment state and last error.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "type": "function",
            "name": "get_event_history",
            "description": "Get the transaction's ordered event history. Events include occurrence and receive times.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "type": "function",
            "name": "check_duplicate_payment",
            "description": "Check whether multiple captured payment IDs appear for the transaction.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "type": "function",
            "name": "list_evidence",
            "description": "List the structured evidence bundle used for the investigation.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
    ]


def _call_tool(tools: InvestigationTools, name: str, args: Dict[str, Any]) -> Any:
    if args:
        raise ValueError(f"PAYGUARD tools do not accept arguments in this MVP: {name}")
    fn: Optional[Callable[[], Any]] = getattr(tools, name, None)
    if fn is None:
        raise ValueError(f"Unknown investigation tool: {name}")
    return fn()


def _diagnosis_schema() -> Dict[str, Any]:
    return {
        "type": "object",
        "properties": {
            "incident_type": {"type": "string"},
            "root_cause": {"type": "string"},
            "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            "summary": {"type": "string"},
            "evidence": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "fact": {"type": "string"},
                        "value": {},
                        "source": {"type": "string"},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["fact", "value", "source", "confidence"],
                    "additionalProperties": False,
                },
            },
            "candidate_actions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "action_type": {"type": "string"},
                        "reason": {"type": "string"},
                        "expected_recovery": {"type": "integer", "minimum": 0},
                        "expected_cost": {"type": "integer", "minimum": 0},
                        "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    },
                    "required": ["action_type", "reason", "expected_recovery", "expected_cost", "confidence"],
                    "additionalProperties": False,
                },
            },
            "recommended_action": {"type": "string"},
        },
        "required": [
            "incident_type",
            "root_cause",
            "confidence",
            "summary",
            "evidence",
            "candidate_actions",
            "recommended_action",
        ],
        "additionalProperties": False,
    }


class OpenAIInvestigator:
    """Tool-using LLM investigator with deterministic safety fallback.

    The LLM only investigates and recommends. Financial authorization remains
    outside this class in RecoveryPolicy.
    """

    def __init__(self, model: Optional[str] = None, client: Any = None) -> None:
        self.model = model or os.getenv("PAYGUARD_MODEL", "gpt-5.6-luna")
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            return None
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("OpenAI SDK is not installed. Run: pip install -r requirements.txt") from exc
        self._client = OpenAI(api_key=api_key)
        return self._client

    def investigate(self, incident: Incident, state: TransactionState, tools: InvestigationTools) -> DiagnosisOutput:
        client = self.client
        if client is None:
            deterministic = DeterministicInvestigator().investigate(incident, tools)
            sanitized, _warnings = sanitize_diagnosis(deterministic, state)
            return self._from_deterministic(sanitized)

        tool_outputs: List[Dict[str, Any]] = []
        input_items: List[Dict[str, Any]] = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "incident": asdict(incident),
                        "projected_state": {
                            "payment": asdict(state.payment),
                            "order": asdict(state.order),
                            "inventory": asdict(state.inventory),
                            "fulfillment": asdict(state.fulfillment),
                        },
                        "instruction": "Investigate this incident. Use tools to verify evidence before diagnosing.",
                    },
                    default=str,
                ),
            },
        ]

        for _ in range(6):
            response = client.responses.create(
                model=self.model,
                input=input_items,
                tools=_tool_specs(),
            )
            input_items.extend([item.model_dump() if hasattr(item, "model_dump") else item for item in response.output])

            function_calls = [item for item in response.output if getattr(item, "type", None) == "function_call"]
            if not function_calls:
                break

            for call in function_calls:
                name = getattr(call, "name")
                args = json.loads(getattr(call, "arguments", "{}"))
                result = _call_tool(tools, name, args)
                tool_outputs.append({"tool": name, "result": result})
                input_items.append(
                    {
                        "type": "function_call_output",
                        "call_id": getattr(call, "call_id"),
                        "output": json.dumps(result, default=str),
                    }
                )
        else:
            raise RuntimeError("LLM investigation exceeded the tool-call limit")

        structured = client.responses.create(
            model=self.model,
            input=input_items
            + [
                {
                    "role": "user",
                    "content": "Return the final diagnosis now. Use only evidence you actually verified. Do not claim execution.",
                }
            ],
            text={"format": {"type": "json_schema", "name": "payguard_diagnosis", "schema": _diagnosis_schema(), "strict": True}},
        )
        raw = structured.output_text
        try:
            parsed = DiagnosisOutput.model_validate_json(raw)
            diagnosis = Diagnosis(
                incident_type=parsed.incident_type,
                root_cause=parsed.root_cause,
                confidence=parsed.confidence,
                evidence=[e.model_dump() for e in parsed.evidence],
                candidate_actions=[CandidateAction(**a.model_dump()) for a in parsed.candidate_actions],
            )
            sanitized, _warnings = sanitize_diagnosis(diagnosis, state)
            return DiagnosisOutput(
                incident_type=sanitized.incident_type,
                root_cause=sanitized.root_cause,
                confidence=sanitized.confidence,
                summary=parsed.summary,
                evidence=[EvidenceClaim(**e) for e in sanitized.evidence],
                candidate_actions=[AIAction(**asdict(a)) for a in sanitized.candidate_actions],
                recommended_action=(parsed.recommended_action if parsed.recommended_action in {a.action_type for a in sanitized.candidate_actions} else sanitized.candidate_actions[0].action_type),
            )
        except ValidationError as exc:
            raise RuntimeError(f"LLM returned invalid PAYGUARD diagnosis: {exc}") from exc

    @staticmethod
    def _from_deterministic(diagnosis: Diagnosis) -> DiagnosisOutput:
        return DiagnosisOutput(
            incident_type=diagnosis.incident_type,
            root_cause=diagnosis.root_cause,
            confidence=diagnosis.confidence,
            summary="Deterministic fallback used because no OpenAI API key is configured.",
            evidence=[EvidenceClaim(fact=x["fact"], value=x["value"], source=x["source"], confidence=0.99) for x in diagnosis.evidence],
            candidate_actions=[AIAction(**asdict(a)) for a in diagnosis.candidate_actions],
            recommended_action=diagnosis.candidate_actions[0].action_type if diagnosis.candidate_actions else "ESCALATE_HUMAN",
        )
