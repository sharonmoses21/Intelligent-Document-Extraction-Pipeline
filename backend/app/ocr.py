from __future__ import annotations

from io import BytesIO
import subprocess

import pymupdf
from PIL import Image, ImageOps


MAX_PDF_PAGES = 20
MAX_IMAGE_PIXELS = 25_000_000
Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS


def _tesseract(image: Image.Image) -> str:
    image = ImageOps.autocontrast(image.convert("L"))
    image = image.point(lambda pixel: 255 if pixel > 170 else 0)
    prepared = BytesIO()
    image.save(prepared, format="PNG")
    try:
        result = subprocess.run(
            ["tesseract", "stdin", "stdout", "--psm", "6"],
            input=prepared.getvalue(),
            capture_output=True,
            check=True,
            timeout=30,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("Tesseract OCR is not installed") from exc
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("OCR exceeded its time limit") from exc
    except subprocess.CalledProcessError as exc:
        raise RuntimeError("Tesseract could not process the uploaded image") from exc
    return result.stdout.decode("utf-8", errors="replace").strip()


def extract_text(content: bytes, filename: str) -> str:
    suffix = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if suffix == "pdf":
        try:
            document = pymupdf.open(stream=content, filetype="pdf")
        except Exception as exc:
            raise ValueError("The uploaded PDF could not be opened") from exc
        with document:
            if document.page_count == 0 or document.page_count > MAX_PDF_PAGES:
                raise ValueError(f"PDFs must contain between 1 and {MAX_PDF_PAGES} pages")
            pages = []
            for page in document:
                page_text = page.get_text().strip()
                if not page_text:
                    page_area = max(page.rect.width * page.rect.height, 1)
                    scale = min(2.0, (MAX_IMAGE_PIXELS / page_area) ** 0.5)
                    image_bytes = page.get_pixmap(matrix=pymupdf.Matrix(scale, scale)).tobytes("png")
                    with Image.open(BytesIO(image_bytes)) as image:
                        page_text = _tesseract(image)
                pages.append(page_text)
            return "\n".join(page for page in pages if page).strip()

    if suffix not in {"png", "jpg", "jpeg", "tif", "tiff"}:
        raise ValueError("Only PDF, PNG, JPEG, and TIFF documents are supported")
    try:
        with Image.open(BytesIO(content)) as image:
            if image.width * image.height > MAX_IMAGE_PIXELS:
                raise ValueError("The uploaded image exceeds the pixel limit")
            image.load()
            return _tesseract(image)
    except ValueError:
        raise
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("The uploaded image could not be opened safely") from exc
