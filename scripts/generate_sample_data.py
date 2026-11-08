import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate synthetic invoice OCR samples")
    parser.add_argument("--out", default="backend/eval/data")
    parser.add_argument("--count", type=int, default=30)
    args = parser.parse_args()
    if args.count < 1:
        parser.error("--count must be at least 1")
    output = Path(args.out)
    output.mkdir(parents=True, exist_ok=True)
    with (output / "samples.jsonl").open("w", encoding="utf-8") as samples:
        for index in range(1, args.count + 1):
            invoice_number = f"INV-{index:04d}"
            date = f"2025-{(index - 1) % 12 + 1:02d}-15"
            total = f"{index * 12.50:.2f}"
            vendor = f"Sample Vendor {index:02d}"
            expected_review = index % 5 == 0
            text = (
                f"{vendor}\nInvoice Number: {invoice_number}\n"
                f"Invoice Date: {date}\n"
                + ("" if expected_review else f"Total Due: ${total}\n")
            )
            samples.write(
                json.dumps(
                    {
                        "text": text,
                        "ground_truth": {
                            "vendor_name": vendor,
                            "invoice_number": invoice_number,
                            "invoice_date": date,
                            "total": None if expected_review else total,
                        },
                        "expected_review": expected_review,
                    }
                )
                + "\n"
            )


if __name__ == "__main__":
    main()
