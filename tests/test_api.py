from fastapi.testclient import TestClient

from backend.app import main
from backend.app.database import Correction, Document, SessionLocal


def test_upload_review_and_correction(monkeypatch):
    monkeypatch.setattr(
        main,
        "extract_text",
        lambda content, filename: (
            "Acme Supplies\nInvoice Number: INV-1042\nInvoice Date: 2025-03-14\nTotal Due: $20.00"
        ),
    )
    client = TestClient(main.app)
    with SessionLocal() as db:
        db.query(Correction).delete()
        db.query(Document).delete()
        db.commit()

    response = client.post(
        "/api/documents",
        files={"file": ("invoice.pdf", b"pdf bytes", "application/pdf")},
    )

    assert response.status_code == 200
    document = response.json()
    assert document["status"] == "accepted"
    assert client.get("/api/documents/" + document["id"]).status_code == 200

    review_response = client.post(
        "/api/documents/" + document["id"] + "/review",
        json={"corrections": {"total": "21.00"}, "reviewer": "test"},
    )
    assert review_response.status_code == 200
    assert review_response.json()["status"] == "reviewed"
    assert review_response.json()["extracted_data"]["total"] == "21.00"

    with SessionLocal() as db:
        db.query(Correction).filter(Correction.document_id == document["id"]).delete()
        db.query(Document).filter(Document.id == document["id"]).delete()
        db.commit()
