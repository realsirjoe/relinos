import time
import requests
from typing import Any
import os
from decimal import Decimal

from relinos.config import openaiAPIKey


class OpenAIHTTPError(Exception):
    pass

def askOpenai(
    message: str, apiKey: str, 
    model: str = "gpt-5.5",
    system: str | None = None,
    temperature: float | None = None,
    timeout: float = 200.0,
    maxRetries: int = 1,
) -> tuple[str, int, int]:
    body: dict[str, Any] = {
        "model": model, "input": message,
    }

    if system is not None:
        body["instructions"] = system

    if temperature is not None:
        body["temperature"] = temperature

    headers = {
        "Authorization": f"Bearer {apiKey}",
        "Content-Type": "application/json",
    }

    lastError: Exception | None = None

    for attempt in range(maxRetries):
        try:
            r = requests.post(
                "https://api.openai.com/v1/responses",
                headers=headers,
                json=body,
                timeout=timeout,
            )

            if r.status_code in {429, 500, 502, 503, 504}:
                raise OpenAIHTTPError(
                    f"Retryable OpenAI error {r.status_code}: {r.text[:500]}"
                )

            if not r.ok:
                raise OpenAIHTTPError(
                    f"OpenAI error {r.status_code}: {r.text[:1000]}"
                )

            data = r.json()

            inputTokens = data["usage"]["input_tokens"]
            outputTokens = data["usage"]["output_tokens"]

            if isinstance(data.get("output_text"), str):
                return data["output_text"], inputTokens, outputTokens

            chunks: list[str] = []
            for item in data.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") in {"output_text", "text"}:
                        text = content.get("text")
                        if isinstance(text, str):
                            chunks.append(text)

            return "".join(chunks), inputTokens, outputTokens

        except Exception as e:
            lastError = e
            if attempt == maxRetries - 1: break
            time.sleep(2**attempt)

    raise OpenAIHTTPError(f"OpenAI request failed after retries: {lastError}")

def estimateCost(inputTokens: int, outputTokens: int, model: str) -> Decimal:
    '''
    Estimates llm cost based on nr of input tokens, output tokens, and model
    iCostM and oCostM is per million 
    '''
    if model == "gpt-4.1":
        iCostM = 2.00
        oCostM = 8.00
    elif model == "gpt-4.1-mini":
        iCostM = 0.40
        oCostM = 1.60
    elif model == "gpt-4.1-nano":
        iCostM = 0.10
        oCostM = 0.40
    elif model == "gpt-5.2":
        iCostM = 1.75
        oCostM = 14.00
    elif model == "gpt-5.1":
        iCostM = 1.25
        oCostM = 10.00
    else: 
        raise Exception(f"Cannot estimate cost, unsupported model {model}")

    iCost = Decimal(iCostM) / Decimal(1_000_000)
    oCost = Decimal(oCostM) / Decimal(1_000_000)

    return Decimal(inputTokens) * iCost + Decimal(outputTokens) * oCost

if __name__ == "__main__":
    answer, inputTokens, outputTokens = askOpenai(
        apiKey=openaiAPIKey,
        model="gpt-4.1",
        system="You are a concise Python assistant.",
        message="Explain requests.Session in one sentence.",
    )
    print(answer)
    print("Estimated llm cost:", estimateCost(inputTokens, outputTokens, "gpt-4.1"))
