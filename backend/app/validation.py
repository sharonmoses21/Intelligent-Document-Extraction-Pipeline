from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
import re

from .schemas import InvoiceData


def _normalized(value: str) -> str:
    return re.sub(r"[^a-z0-9]", "", value.lower())


def _has_evidence(value: str, text: str) -> bool:
    normalized_value = _normalized(value)
    normalized_text = _normalized(text)
    return bool(normalized_value and normalized_value in normalized_text)


def _date_has_evidence(value: str, text: str) -> bool:
    try:
        parsed = date.fromisoformat(value)
    except ValueError:
        return _has_evidence(value, text)
    formats = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y", "%b %d, %Y", "%B %d, %Y")
    return any(_has_evidence(parsed.strftime(date_format), text) for date_format in formats)


def _amount_has_evidence(value: Decimal, text: str) -> bool:
    for candidate in re.findall(r"(?<!\w)\d[\d,]*(?:\.\d{1,2})?", text):
        try:
            if Decimal(candidate.replace(",", "")) == value:
                return True
        except InvalidOperation:
            continue
    return False


def review_reasons(data: InvoiceData, source_text: str) -> list[str]:
    reasons: list[str] = []
    for field in ("vendor_name", "invoice_number", "invoice_date", "total"):
        if getattr(data, field) is None:
            reasons.append(f"Missing required field: {field}")

    if data.invoice_date:
        try:
            date.fromisoformat(data.invoice_date)
        except ValueError:
            reasons.append("Invoice date is not a valid ISO date")
    if data.total is not None and (not data.total.is_finite() or data.total <= 0):
        reasons.append("Invoice total must be a positive finite amount")
    for index, item in enumerate(data.line_items, start=1):
        if item.quantity is not None and item.quantity <= 0:
            reasons.append(f"Line item {index} quantity must be positive")
        if item.unit_price is not None and item.unit_price < 0:
            reasons.append(f"Line item {index} unit price cannot be negative")
        if item.amount is not None and item.amount < 0:
            reasons.append(f"Line item {index} amount cannot be negative")
        if (
            item.quantity is not None
            and item.unit_price is not None
            and item.amount is not None
            and abs(item.quantity * item.unit_price - item.amount) > Decimal("0.01")
        ):
            reasons.append(f"Line item {index} quantity and unit price do not match its amount")
        if item.description and not _has_evidence(item.description, source_text):
            reasons.append(f"Line item {index} description is not supported by OCR text")

    amounts = [item.amount for item in data.line_items]
    if data.total is not None and amounts and all(amount is not None for amount in amounts):
        if abs(sum(amounts, Decimal("0")) - data.total) > Decimal("0.02"):
            reasons.append("Line item amounts do not match the invoice total")

    for field in ("vendor_name", "invoice_number", "invoice_date"):
        value = getattr(data, field)
        supported = _date_has_evidence(value, source_text) if field == "invoice_date" and value else (
            _has_evidence(value, source_text) if value else True
        )
        if value and not supported:
            reasons.append(f"Extracted {field} is not supported by OCR text")
    if data.currency:
        currency_markers = {
            "USD": (r"\bUSD\b", r"\$"),
            "EUR": (r"\bEUR\b", "€"),
            "GBP": (r"\bGBP\b", "£"),
            "CAD": (r"\bCAD\b", r"\bC\$"),
            "AUD": (r"\bAUD\b", r"\bA\$"),
        }
        markers = currency_markers.get(data.currency.upper(), (rf"\b{re.escape(data.currency)}\b",))
        if not any(re.search(marker, source_text, re.IGNORECASE) for marker in markers):
            reasons.append("Extracted currency is not supported by OCR text")
    if data.total is not None and data.total.is_finite():
        if not _amount_has_evidence(data.total, source_text):
            reasons.append("Extracted total is not supported by OCR text")
    if data.confidence < 0.75:
        reasons.append("Extraction confidence is below the review threshold")
    return reasons
