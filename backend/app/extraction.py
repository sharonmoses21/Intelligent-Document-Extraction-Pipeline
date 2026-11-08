from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
import json
import os
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .schemas import InvoiceData


EXTRACTION_PROMPT = """Extract invoice or receipt fields from the OCR text.
Return only a JSON object with vendor_name, invoice_number, invoice_date, total,
currency, line_items (objects with description, quantity, unit_price, amount),
and confidence (0 to 1). Use null for unknown values. Never infer missing facts.
OCR text:
"""


def _first(pattern: str, text: str, flags: int = re.IGNORECASE) -> str | None:
    match = re.search(pattern, text, flags)
    return match.group(1).strip(" \t:#") if match else None


def mock_extract(text: str) -> InvoiceData:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    vendor = lines[0] if lines else None
    number = _first(
        r"(?:invoice|receipt)\s*(?:no\.?|number|#)\s*[:#-]?\s*([A-Z0-9][A-Z0-9/-]*)",
        text,
    )
    raw_date = _first(
        r"(?:date|issued)\s*[:#-]?\s*([A-Z0-9,./ -]{6,24})",
        text,
    )
    invoice_date = None
    if raw_date:
        raw_date = raw_date.strip()
        for date_format in ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%b %d, %Y", "%B %d, %Y"):
            try:
                invoice_date = datetime.strptime(raw_date, date_format).date().isoformat()
                break
            except ValueError:
                continue
        if invoice_date is None:
            invoice_date = raw_date

    amount_text = _first(
        r"(?:grand\s+total|total\s+due|amount\s+due|total)\s*[:$ ]+\s*"
        r"(?:USD|EUR|GBP|CAD|AUD)?\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)",
        text,
    )
    try:
        total = Decimal(amount_text.replace(",", "")) if amount_text else None
    except InvalidOperation:
        total = None
    currency = _first(r"\b(USD|EUR|GBP|CAD|AUD)\b", text)
    if currency is None and "$" in text:
        currency = "USD"
    line_items = []
    item_pattern = re.compile(
        r"^(.+?)\s+(\d+(?:\.\d+)?)\s+\$?([\d,]+\.\d{2})\s+\$?([\d,]+\.\d{2})$"
    )
    for line in lines:
        item = item_pattern.match(line)
        if item:
            line_items.append(
                {
                    "description": item.group(1).strip(),
                    "quantity": item.group(2),
                    "unit_price": item.group(3).replace(",", ""),
                    "amount": item.group(4).replace(",", ""),
                }
            )
    return InvoiceData(
        vendor_name=vendor,
        invoice_number=number,
        invoice_date=invoice_date,
        total=total,
        currency=currency,
        line_items=line_items,
        confidence=0.85 if all((vendor, number, invoice_date, total)) else 0.35,
    )


def _decode_json(response: str) -> dict:
    response = response.strip()
    if response.startswith("```"):
        response = re.sub(r"^```(?:json)?\s*|\s*```$", "", response, flags=re.IGNORECASE)
    start, end = response.find("{"), response.rfind("}")
    if start < 0 or end < start:
        raise ValueError("The LLM response did not contain a JSON object")
    result = json.loads(response[start : end + 1])
    if not isinstance(result, dict):
        raise ValueError("The LLM response must be a JSON object")
    return result


def _request_json(url: str, headers: dict[str, str], payload: dict) -> dict:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read(2_000_001))
    except (HTTPError, URLError, TimeoutError) as exc:
        raise RuntimeError("The configured LLM provider request failed") from exc


def _provider_response(text: str, provider: str) -> str:
    prompt = EXTRACTION_PROMPT + text[:80_000]
    if provider == "anthropic":
        key = os.getenv("ANTHROPIC_API_KEY")
        if not key:
            raise RuntimeError("ANTHROPIC_API_KEY is required for the Anthropic provider")
        data = _request_json(
            "https://api.anthropic.com/v1/messages",
            {"x-api-key": key, "anthropic-version": "2023-06-01"},
            {
                "model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-20241022"),
                "max_tokens": 1500,
                "messages": [{"role": "user", "content": prompt}],
            },
        )
        return data["content"][0]["text"]
    if provider == "gemini":
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is required for the Gemini provider")
        model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")
        data = _request_json(
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}",
            {},
            {"contents": [{"parts": [{"text": prompt}]}]},
        )
        return data["candidates"][0]["content"]["parts"][0]["text"]
    raise ValueError("LLM_PROVIDER must be mock, anthropic, or gemini")


def extract_invoice(text: str, provider: str | None = None) -> InvoiceData:
    selected_provider = (provider or os.getenv("LLM_PROVIDER", "mock")).lower()
    if selected_provider == "mock":
        return mock_extract(text)
    return InvoiceData.model_validate(_decode_json(_provider_response(text, selected_provider)))
