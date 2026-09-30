"""One model port with Anthropic- and OpenAI-compatible wire adapters."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Protocol
from urllib.parse import urlparse


@dataclass(frozen=True)
class ToolCall:
    """Provider-independent function request returned by one model turn."""

    call_id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class ModelTurn:
    """Normalize text, tool requests, usage, and continuation state."""

    text: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    usage: dict[str, int] = field(default_factory=dict)
    stop_reason: str = ""
    response_items: list[Any] = field(default_factory=list)


class ModelPort(Protocol):
    """Keep the investigation loop independent of provider wire formats."""

    model_name: str

    def generate(
        self,
        system: str,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 5000,
        json_mode: bool = False,
    ) -> ModelTurn:
        """Generate one turn from the shared conversation and tool schema."""
        ...


class AnthropicCompatibleModel:
    """Adapt the shared conversation to Anthropic Messages semantics."""

    def __init__(self, model_name: str, base_url: str | None = None) -> None:
        """Build a client from the configured endpoint and credentials."""
        from anthropic import Anthropic

        # Token and key are alternative credential forms accepted by the SDK.
        token = os.getenv("ANTHROPIC_AUTH_TOKEN")
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not token and not api_key:
            raise RuntimeError("Set ANTHROPIC_AUTH_TOKEN or ANTHROPIC_API_KEY")
        self.model_name = model_name
        self.client = Anthropic(
            auth_token=token or None,
            api_key=api_key or None,
            base_url=base_url or os.getenv("ANTHROPIC_BASE_URL"),
            timeout=float(os.getenv("BB_MODEL_TIMEOUT_SECONDS", "180")),
            max_retries=2,
        )

    @staticmethod
    def _messages(history: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Group tool results as user content, as required by Messages."""
        # Messages is the Anthropic wire representation of shared history.
        messages: list[dict[str, Any]] = []
        for turn in history:
            if turn["role"] == "user":
                messages.append({"role": "user", "content": turn["content"]})
            elif turn["role"] == "assistant":
                # Blocks combine assistant prose with any requested tools.
                blocks: list[dict[str, Any]] = []
                if turn.get("content"):
                    blocks.append({"type": "text", "text": turn["content"]})
                # Call is each assistant tool request carried into this turn.
                for call in turn.get("tool_calls", []):
                    blocks.append(
                        {
                            "type": "tool_use",
                            "id": call["call_id"],
                            "name": call["name"],
                            "input": call["arguments"],
                        }
                    )
                messages.append({"role": "assistant", "content": blocks})
            elif turn["role"] == "tool":
                # Tool results are user-role content in the Messages format.
                block = {
                    "type": "tool_result",
                    "tool_use_id": turn["tool_call_id"],
                    "content": turn["content"],
                }
                if messages and messages[-1]["role"] == "user" and isinstance(messages[-1]["content"], list):
                    messages[-1]["content"].append(block)
                else:
                    messages.append({"role": "user", "content": [block]})
        return messages

    def generate(
        self,
        system: str,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 5000,
        json_mode: bool = False,
    ) -> ModelTurn:
        """Translate tool definitions and normalize a Messages response."""
        # Args is the provider-specific request assembled from the common port.
        args: dict[str, Any] = {
            "model": self.model_name,
            "max_tokens": max_tokens,
            "system": system,
            "messages": self._messages(history),
        }
        if tools:
            # Tool is one provider-neutral function definition.
            args["tools"] = [
                {
                    "name": tool["name"],
                    "description": tool["description"],
                    "input_schema": tool["parameters"],
                }
                for tool in tools
            ]
        # Response is the raw Messages result, normalized below.
        response = self.client.messages.create(**args)
        # Text concatenates assistant text blocks without tool payloads.
        text = "\n".join(block.text for block in response.content if block.type == "text")
        # Calls preserves function identifiers and parsed arguments.
        calls = [
            ToolCall(call_id=block.id, name=block.name, arguments=block.input)
            for block in response.content
            if block.type == "tool_use"
        ]
        # Usage is a provider-neutral input/output token pair.
        usage = {
            "input_tokens": int(response.usage.input_tokens or 0),
            "output_tokens": int(response.usage.output_tokens or 0),
        }
        return ModelTurn(text=text, tool_calls=calls, usage=usage, stop_reason=response.stop_reason or "")


class OpenAICompatibleModel:
    """Adapt the same model port to OpenAI-compatible endpoints."""

    def __init__(self, model_name: str, base_url: str | None = None) -> None:
        """Select the credential associated with the effective endpoint."""
        from openai import OpenAI

        # Endpoint chooses the compatible service used by this adapter.
        endpoint = base_url or os.getenv("OPENAI_BASE_URL")
        if not endpoint and not os.getenv("OPENAI_API_KEY"):
            endpoint = os.getenv("ZAI_BASE_URL")
        # Key name follows the effective host so credentials are not mixed.
        key_name = "ZAI_API_KEY" if endpoint and urlparse(endpoint).hostname == "api.z.ai" else "OPENAI_API_KEY"
        # Key is read only at client construction, never written to artifacts.
        key = os.getenv(key_name)
        if not key:
            raise RuntimeError(f"Set {key_name}")
        self.model_name = model_name
        self.client = OpenAI(
            api_key=key,
            base_url=endpoint,
            timeout=float(os.getenv("BB_MODEL_TIMEOUT_SECONDS", "180")),
            max_retries=2,
        )

    def generate(
        self,
        system: str,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        max_tokens: int = 5000,
        json_mode: bool = False,
    ) -> ModelTurn:
        """Use Responses where supported, otherwise Chat Completions."""
        if self.model_name.startswith("gpt-6-") and urlparse(str(self.client.base_url)).hostname == "api.openai.com":
            return self._generate_responses(system, history, tools, max_tokens, json_mode)
        # Messages translates the shared history to Chat Completions roles.
        messages: list[dict[str, Any]] = [{"role": "system", "content": system}]
        for turn in history:
            if turn["role"] in ("user", "assistant"):
                # Payload retains assistant tool calls beside assistant text.
                payload: dict[str, Any] = {"role": turn["role"], "content": turn.get("content") or ""}
                if turn["role"] == "assistant" and turn.get("tool_calls"):
                    # Call is one assistant function request in shared history.
                    payload["tool_calls"] = [
                        {
                            "id": call["call_id"],
                            "type": "function",
                            "function": {
                                "name": call["name"],
                                "arguments": json.dumps(call["arguments"]),
                            },
                        }
                        for call in turn["tool_calls"]
                    ]
                messages.append(payload)
            elif turn["role"] == "tool":
                messages.append(
                    {
                        "role": "tool",
                        "tool_call_id": turn["tool_call_id"],
                        "content": turn["content"],
                    }
                )
        # Args contains only capabilities supported by this wire endpoint.
        args: dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "max_tokens": max_tokens,
        }
        if tools:
            # Tool is one function made available for Chat Completions.
            args["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool["name"],
                        "description": tool["description"],
                        "parameters": tool["parameters"],
                    },
                }
                for tool in tools
            ]
        if json_mode:
            args["response_format"] = {"type": "json_object"}
        # Thinking mode is optional and defaults off for the GLM family here.
        thinking_mode = os.getenv("BB_GLM_THINKING")
        if not thinking_mode and self.model_name.lower().startswith("glm-4.7"):
            thinking_mode = "disabled"
        if thinking_mode:
            if thinking_mode not in {"enabled", "disabled"}:
                raise ValueError("BB_GLM_THINKING must be enabled or disabled")
            args["extra_body"] = {"thinking": {"type": thinking_mode}}
        # Response is the raw completion; message contains its first choice.
        response = self.client.chat.completions.create(**args)
        message = response.choices[0].message
        # Calls converts JSON-encoded arguments back to dictionaries.
        calls = [
            ToolCall(
                call_id=call.id,
                name=call.function.name,
                arguments=json.loads(call.function.arguments),
            )
            for call in (message.tool_calls or [])
        ]
        # Usage may be absent on some compatible endpoints.
        usage = response.usage
        return ModelTurn(
            text=message.content or "",
            tool_calls=calls,
            usage={
                "input_tokens": int(usage.prompt_tokens) if usage else 0,
                "output_tokens": int(usage.completion_tokens) if usage else 0,
            },
            stop_reason=response.choices[0].finish_reason or "",
        )

    def _generate_responses(
        self,
        system: str,
        history: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None,
        max_tokens: int,
        json_mode: bool,
    ) -> ModelTurn:
        """Preserve Responses output items across tool turns for continuity."""
        # Inputs replays assistant output items and function results in order.
        inputs: list[Any] = []
        for turn in history:
            if turn["role"] == "assistant" and turn.get("response_items"):
                inputs.extend(turn["response_items"])
            elif turn["role"] in ("user", "assistant"):
                if turn.get("content"):
                    inputs.append({"role": turn["role"], "content": turn["content"]})
                # Call is an assistant function request replayed in order.
                for call in turn.get("tool_calls", []):
                    inputs.append({
                        "type": "function_call",
                        "call_id": call["call_id"],
                        "name": call["name"],
                        "arguments": json.dumps(call["arguments"]),
                    })
            elif turn["role"] == "tool":
                inputs.append({
                    "type": "function_call_output",
                    "call_id": turn["tool_call_id"],
                    "output": turn["content"],
                })
        # Args asks the Responses API for a stateless, auditable continuation.
        args: dict[str, Any] = {
            "model": self.model_name,
            "instructions": system,
            "input": inputs,
            "max_output_tokens": max_tokens + 2000,
            "reasoning": {"effort": os.getenv("BB_OPENAI_REASONING_EFFORT", "medium")},
            "store": False,
            "include": ["reasoning.encrypted_content"],
        }
        if tools:
            # Tool is one function exposed through the Responses interface.
            args["tools"] = [
                {
                    "type": "function",
                    "name": tool["name"],
                    "description": tool["description"],
                    "parameters": tool["parameters"],
                    "strict": False,
                }
                for tool in tools
            ]
        if json_mode:
            inputs.append({"role": "user", "content": "Return one valid JSON object."})
            args["text"] = {"format": {"type": "json_object"}}
        # Response carries opaque output items needed by later tool turns.
        response = self.client.responses.create(**args)
        # Calls extracts function requests while preserving raw output separately.
        calls = [
            ToolCall(call_id=item.call_id, name=item.name, arguments=json.loads(item.arguments))
            for item in response.output if item.type == "function_call"
        ]
        return ModelTurn(
            text=response.output_text,
            tool_calls=calls,
            usage={
                "input_tokens": int(response.usage.input_tokens) if response.usage else 0,
                "output_tokens": int(response.usage.output_tokens) if response.usage else 0,
            },
            stop_reason=response.status or "",
            response_items=list(response.output),
        )


def make_model(provider: str, model_name: str, base_url: str | None = None) -> ModelPort:
    """Construct the configured adapter behind the stable model port."""
    if provider == "anthropic":
        return AnthropicCompatibleModel(model_name, base_url)
    if provider == "openai":
        return OpenAICompatibleModel(model_name, base_url)
    raise ValueError(f"Unsupported provider: {provider}")


def parse_json_object(text: str) -> dict[str, Any]:
    """Extract one JSON object without accepting trailing model prose as data."""
    # Stripped is the candidate body after optional Markdown-fence removal.
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.split("\n", 1)[1].rsplit("```", 1)[0].strip()
    if not stripped.startswith("{"):
        # First and last bracket positions isolate an embedded object.
        first = stripped.find("{")
        last = stripped.rfind("}")
        if first < 0 or last <= first:
            raise ValueError("Model did not return a JSON object")
        stripped = stripped[first : last + 1]
    # Value must be a mapping to satisfy downstream stage contracts.
    value = json.loads(stripped)
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def generate_json(
    model: ModelPort,
    system: str,
    user: str,
    max_tokens: int,
    attempts: int = 2,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """Request structured output and retain usage for every repair attempt."""
    # History includes feedback so a malformed response can be corrected.
    history: list[dict[str, Any]] = [{"role": "user", "content": user}]
    # Trace records usage and stop reason for each model attempt.
    trace: list[dict[str, Any]] = []
    for attempt in range(attempts):
        # Turn is one model response, valid or invalid.
        turn = model.generate(system, history, max_tokens=max_tokens, json_mode=True)
        trace.append({"stage": "json", "attempt": attempt + 1, "usage": turn.usage, "stop_reason": turn.stop_reason})
        try:
            return parse_json_object(turn.text), trace
        except (ValueError, json.JSONDecodeError) as error:
            history.extend(
                [
                    {"role": "assistant", "content": turn.text, "response_items": turn.response_items},
                    {"role": "user", "content": f"Your output was not valid JSON: {error}. Return one complete JSON object only."},
                ]
            )
    raise ValueError("Model failed to return valid JSON after retry")
