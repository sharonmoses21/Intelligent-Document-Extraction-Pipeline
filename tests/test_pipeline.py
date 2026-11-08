from decimal import Decimal

import pymupdf

from backend.app.extraction import mock_extract
from backend.app.ocr import extract_text
from backend.app.schemas import InvoiceData, LineItem
from backend.app.validation import review_reasons
from backend.eval.run_eval import evaluate


SAMPLE_TEXT = """Acme Supplies
Invoice Number: INV-1042
Invoice Date: 2025-03-14
Widget 2 10.00 20.00
Total Due: $20.00
"""


def test_mock_extraction_and_validation_accept_supported_invoice():
    extracted = mock_extract(SAMPLE_TEXT)

    assert extracted.vendor_name == "Acme Supplies"
    assert extracted.invoice_number == "INV-1042"
    assert extracted.invoice_date == "2025-03-14"
    assert extracted.total == Decimal("20.00")
    assert extracted.line_items[0].description == "Widget"
    assert review_reasons(extracted, SAMPLE_TEXT) == []


def test_validation_flags_unsupported_values_and_total_mismatch():
    extracted = InvoiceData(
        vendor_name="Invented Vendor",
        invoice_number="INV-9999",
        invoice_date="2025-03-14",
        total=Decimal("27.00"),
        confidence=0.9,
        line_items=[
            LineItem(description="Widget", quantity=2, unit_price=10, amount=Decimal("20"))
        ],
    )

    reasons = review_reasons(extracted, SAMPLE_TEXT)

    assert "Extracted vendor_name is not supported by OCR text" in reasons
    assert "Extracted invoice_number is not supported by OCR text" in reasons
    assert "Extracted total is not supported by OCR text" in reasons
    assert "Line item amounts do not match the invoice total" in reasons


def test_invoice_number_or_date_digits_do_not_support_a_total():
    text = "Acme Supplies\nInvoice Number: INV-2025\nInvoice Date: 2025-03-14"
    extracted = InvoiceData(
        vendor_name="Acme Supplies",
        invoice_number="INV-2025",
        invoice_date="2025-03-14",
        total=Decimal("2025"),
        confidence=0.9,
    )

    assert "Extracted total is not supported by OCR text" in review_reasons(extracted, text)


def test_pdf_text_is_extracted_without_ocr():
    pdf = pymupdf.open()
    page = pdf.new_page()
    page.insert_text((72, 72), "Readable invoice text")
    content = pdf.tobytes()
    pdf.close()

    assert extract_text(content, "invoice.pdf") == "Readable invoice text"


def test_evaluation_reports_review_metrics(tmp_path):
    dataset = tmp_path / "samples.jsonl"
    dataset.write_text(
        "\n".join(
            [
                '{"text":"Acme\\nInvoice Number: INV-1\\nInvoice Date: 2025-03-14\\nTotal: $20.00","ground_truth":{"vendor_name":"Acme","invoice_number":"INV-1","invoice_date":"2025-03-14","total":"20.00"},"expected_review":false}',
                '{"text":"Acme\\nInvoice Number: INV-2\\nInvoice Date: 2025-03-14","ground_truth":{"vendor_name":"Acme","invoice_number":"INV-2","invoice_date":"2025-03-14","total":null},"expected_review":true}',
            ]
        ),
        encoding="utf-8",
    )

    metrics = evaluate(dataset)

    assert metrics["status_detection_accuracy"] == 1.0
    assert metrics["review_flag_catch_rate"] == 1.0
    assert metrics["false_positive_review_rate"] == 0.0
    assert metrics["manual_review_rate"] == 0.5
