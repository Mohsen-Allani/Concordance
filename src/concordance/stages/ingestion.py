from pathlib import Path

import pymupdf


def ingest(pdf_path: Path, pages_dir: Path, dpi: int) -> list[dict]:
    pages_dir.mkdir(parents=True, exist_ok=True)
    doc = pymupdf.open(pdf_path)
    matrix = pymupdf.Matrix(dpi / 72, dpi / 72)
    results = []
    for i, page in enumerate(doc):
        image_path = pages_dir / f"page_{i + 1:02d}.png"
        page.get_pixmap(matrix=matrix).save(str(image_path))
        results.append({
            "page": i + 1,
            "image": str(image_path),
            "chars": len(page.get_text().strip()),
        })
    doc.close()
    return results
