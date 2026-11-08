from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from pydantic import ValidationError

from .database import Correction, Document, SessionLocal, create_tables
from .extraction import extract_invoice
from .ocr import extract_text
from .schemas import InvoiceData, ReviewRequest
from .validation import review_reasons


MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
ALLOWED_EXTENSIONS = {"pdf", "png", "jpg", "jpeg", "tif", "tiff"}
REVIEW_PAGE = Path(__file__).with_name("review.html")
app = FastAPI(title="Intelligent Document Extraction Pipeline", version="1.0.0")
create_tables()


def _document_response(document: Document) -> dict:
    return {
        "id": document.id,
        "filename": document.filename,
        "status": document.status,
        "extracted_data": json.loads(document.extracted_data),
        "review_reasons": json.loads(document.review_reasons),
        "source_text": document.ocr_text,
        "created_at": document.created_at.isoformat(),
    }


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.post("/api/documents")
async def upload_document(file: UploadFile = File(...)) -> dict:
    filename = Path((file.filename or "upload").replace("\\", "/")).name
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix not in ALLOWED_EXTENSIONS:
        raise HTTPException(415, "Only PDF, PNG, JPEG, and TIFF documents are supported")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if not content:
        raise HTTPException(400, "The uploaded document is empty")
    if len(content) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, f"Documents must be no larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    try:
        ocr_text = extract_text(content, filename)
    except ValueError as exc:
        raise HTTPException(422, str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(503, str(exc)) from exc
    if not ocr_text:
        extraction = InvoiceData()
        reasons = ["OCR did not produce readable text"]
    else:
        try:
            extraction = extract_invoice(ocr_text)
            reasons = review_reasons(extraction, ocr_text)
        except (RuntimeError, ValueError, KeyError, IndexError, TypeError) as exc:
            extraction = InvoiceData()
            reasons = [f"Extraction requires manual review: {exc}"]
    status = "needs_review" if reasons else "accepted"
    with SessionLocal() as db:
        document = Document(
            filename=filename,
            status=status,
            ocr_text=ocr_text,
            extracted_data=extraction.model_dump_json(),
            review_reasons=json.dumps(reasons),
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return _document_response(document)


@app.get("/api/documents")
def list_documents() -> list[dict]:
    with SessionLocal() as db:
        return [
            _document_response(document)
            for document in db.query(Document).order_by(Document.created_at.desc()).all()
        ]


@app.get("/api/documents/{document_id}")
def get_document(document_id: str) -> dict:
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        if document is None:
            raise HTTPException(404, "Document not found")
        return _document_response(document)


@app.get("/api/review")
def list_for_review() -> list[dict]:
    with SessionLocal() as db:
        documents = (
            db.query(Document)
            .filter(Document.status == "needs_review")
            .order_by(Document.created_at.desc())
            .all()
        )
        return [_document_response(document) for document in documents]


@app.post("/api/documents/{document_id}/review")
def review_document(document_id: str, request: ReviewRequest) -> dict:
    with SessionLocal() as db:
        document = db.get(Document, document_id)
        if document is None:
            raise HTTPException(404, "Document not found")
        original = json.loads(document.extracted_data)
        try:
            corrected = InvoiceData.model_validate(original | request.corrections)
        except ValidationError as exc:
            raise HTTPException(422, "Corrections do not match the invoice schema") from exc
        db.add(
            Correction(
                document_id=document.id,
                reviewer=request.reviewer[:100],
                corrections=json.dumps(request.corrections, default=str),
            )
        )
        document.extracted_data = corrected.model_dump_json()
        document.review_reasons = json.dumps(review_reasons(corrected, document.ocr_text))
        document.status = "reviewed"
        db.commit()
        db.refresh(document)
        return _document_response(document)


@app.get("/review", response_class=HTMLResponse)
def review_dashboard() -> HTMLResponse:
    return HTMLResponse(REVIEW_PAGE.read_text(encoding="utf-8"))
