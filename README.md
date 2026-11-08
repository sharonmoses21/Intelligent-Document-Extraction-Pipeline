# Intelligent Document Extraction Pipeline

An OCR- and LLM-powered API for extracting invoice and receipt data, validating it against source text and business rules, and routing uncertain results to human review.

## Features

- Extracts text from text-based and scanned PDFs, plus PNG, JPEG, and TIFF images. Scanned pages are preprocessed and passed to Tesseract.
- Extracts vendor, invoice number, invoice date, total, currency, and line items. The default mock provider is useful for local development; Anthropic and Gemini are configurable.
- Validates required fields, date and amount constraints, line-item totals, extraction confidence, and whether values are supported by OCR text.
- Persists documents and reviewer corrections in SQLite.
- Provides a review page at `/review`, JSON API at `/api`, and OpenAPI docs at `/docs`.

## Run with Docker

```bash
cp .env.example .env
docker compose up --build
```

Open [http://localhost:8000](http://localhost:8000), [the review dashboard](http://localhost:8000/review), or [API docs](http://localhost:8000/docs). The mock provider requires no API key. To use a real provider, set `LLM_PROVIDER=anthropic` or `LLM_PROVIDER=gemini` and provide its API key in `.env`.

## Run locally

Install Tesseract OCR and Python 3.12+, then:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
uvicorn backend.app.main:app --reload
```

Set environment variables from `.env.example` in your shell when using a non-default configuration. SQLite defaults to `backend/data/documents.db`.

### API overview

- `POST /api/documents` — upload a supported document as multipart field `file`
- `GET /api/documents` and `GET /api/documents/{id}` — list or view extraction results
- `GET /api/review` — list documents requiring review
- `POST /api/documents/{id}/review` — submit corrections, for example `{"reviewer":"name","corrections":{"total":"12.50"}}`

Uploads are limited to 10 MB by default and PDFs to 20 pages. Set `MAX_UPLOAD_MB` to change the upload limit.

## Tests and evaluation

```bash
pip install -r requirements-dev.txt
pytest
```

Generate synthetic OCR text and labels, then run the mock-provider evaluation:

```bash
python3 scripts/generate_sample_data.py --out backend/eval/data --count 30
cd backend
python3 -m eval.run_eval
```

The evaluation reports field-level and status-detection accuracy only for synthetic samples. Real-document performance must be measured against verified real-document ground truth; synthetic results are not a claim of production accuracy.
