# Intelligent Document Extraction Pipeline

An AI-powered document processing system that extracts structured information from invoices and receipts using **Optical Character Recognition (OCR), Large Language Models (LLMs), and automated validation**. The pipeline transforms unstructured documents into reliable, structured records while detecting extraction errors and identifying documents requiring manual review.

## Key Features

- **Document Processing:** Extracts information from PDF invoices and scanned receipt images.
- **OCR Integration:** Uses Tesseract OCR with image preprocessing to recognize text.
- **LLM-Based Extraction:** Uses Claude or Gemini to extract vendor names, invoice numbers, dates, totals, and line items.
- **Structured Data Validation:** Uses Pydantic schemas and business rules to validate extracted information.
- **Hallucination Detection:** Checks extracted field evidence against the original OCR text.
- **Human-in-the-Loop Review:** Flags missing, inconsistent, or low-confidence fields for manual verification.
- **Database Integration:** Stores document records and correction history using SQLAlchemy.
- **Evaluation Framework:** Measures field-level accuracy, review-flag effectiveness, and extraction reliability.
- **API and Dashboard:** Provides FastAPI endpoints and web interfaces for document uploads and reviewer workflows.

## Technology Stack

| Component | Technology |
|---|---|
| Programming Language | Python |
| OCR Engine | Tesseract OCR |
| Language Models | Claude / Gemini |
| API Framework | FastAPI |
| Data Validation | Pydantic |
| Database | SQLAlchemy / SQLite |
| Testing | Pytest |
| Containerization | Docker |
| Deployment | Render |

## Processing Architecture

```text
PDF / Scanned Invoice / Receipt
              |
              v
     Document Upload
              |
              v
      OCR Extraction
              |
              v
      LLM Field Extraction
              |
              v
     Structured JSON Output
              |
              v
   Source Evidence Verification
              |
              v
    Business Rule Validation
              |
        +-----+-----+
        |           |
        v           v
    Valid Data   Flagged Data
        |           |
        v           v
    Database    Human Review
                    |
                    v
              Corrections
                    |
                    v
              Database
```

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/YOUR_USERNAME/Intelligent-Document-Extraction-Pipeline.git
cd Intelligent-Document-Extraction-Pipeline
```

### 2. Configure Environment Variables

```bash
cp .env.example .env
```

Configure an LLM provider in `.env`, using `LLM_PROVIDER=gemini`, `LLM_PROVIDER=anthropic`, or `LLM_PROVIDER=mock`. Add the corresponding API key when using a real provider.

### 3. Run the Application

```bash
docker compose up --build

## Evaluation Metrics

The system evaluates extraction reliability using:

- **Field-Level Accuracy:** Percentage of extracted fields matching verified ground truth.
- **Status Detection Accuracy:** Correct identification of document processing outcomes.
- **Review Flag Catch Rate:** Percentage of problematic extractions correctly flagged.
- **False Positive Review Rate:** Percentage of valid extractions unnecessarily flagged.
- **Manual Review Rate:** Percentage of processed documents requiring human verification.

### Run Evaluation

```bash
python3 scripts/generate_sample_data.py --out backend/eval/data --count 30
cd backend
python3 -m eval.run_eval
```

Evaluation results should be reported using verified test data. Synthetic samples can support development, but real-document accuracy must be measured separately.
