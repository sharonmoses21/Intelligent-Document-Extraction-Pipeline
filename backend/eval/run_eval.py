import argparse
import json
from pathlib import Path

if __package__ == "eval":
    from app.extraction import mock_extract
    from app.validation import review_reasons
else:
    from backend.app.extraction import mock_extract
    from backend.app.validation import review_reasons


FIELDS = ("vendor_name", "invoice_number", "invoice_date", "total")


def evaluate(dataset: Path) -> dict:
    compared = 0
    correct = 0
    status_correct = 0
    expected_review_count = 0
    review_caught = 0
    false_positives = 0
    expected_valid_count = 0
    review_count = 0
    for line in dataset.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        sample = json.loads(line)
        extracted = mock_extract(sample["text"])
        prediction = extracted.model_dump(mode="json")
        truth = sample["ground_truth"]
        for field in FIELDS:
            compared += 1
            actual = str(prediction.get(field) or "").strip().lower()
            expected = str(truth.get(field) or "").strip().lower()
            correct += actual == expected
        predicted_review = bool(review_reasons(extracted, sample["text"]))
        expected_review = bool(sample.get("expected_review", False))
        review_count += predicted_review
        status_correct += predicted_review == expected_review
        expected_review_count += expected_review
        expected_valid_count += not expected_review
        review_caught += predicted_review and expected_review
        false_positives += predicted_review and not expected_review
    return {
        "documents": expected_review_count + expected_valid_count,
        "field_level_accuracy": correct / compared if compared else 0.0,
        "status_detection_accuracy": status_correct / (expected_review_count + expected_valid_count)
        if expected_review_count + expected_valid_count
        else 0.0,
        "review_flag_catch_rate": review_caught / expected_review_count if expected_review_count else 0.0,
        "false_positive_review_rate": false_positives / expected_valid_count if expected_valid_count else 0.0,
        "manual_review_rate": review_count / (expected_review_count + expected_valid_count)
        if expected_review_count + expected_valid_count
        else 0.0,
        "note": "Synthetic/mock-provider evaluation; not a measure of real-document accuracy.",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate extraction on a JSONL labeled dataset")
    parser.add_argument("--data", default="eval/data/samples.jsonl")
    args = parser.parse_args()
    result = evaluate(Path(args.data))
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
