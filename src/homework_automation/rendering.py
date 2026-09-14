from __future__ import annotations

import os
import shutil
import subprocess
import importlib.util
from pathlib import Path


def _find_libreoffice() -> str | None:
    candidates = [
        shutil.which("soffice"),
        shutil.which("libreoffice"),
        r"C:\Program Files\LibreOffice\program\soffice.exe",
        r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
        "/Applications/LibreOffice.app/Contents/MacOS/soffice",
    ]
    return next((candidate for candidate in candidates if candidate and Path(candidate).exists()), None)


def renderer_status() -> dict[str, object]:
    return {
        "libreoffice": _find_libreoffice(),
        "pywin32": importlib.util.find_spec("win32com") is not None,
    }


def _convert_with_word(docx_path: Path, pdf_path: Path) -> bool:
    try:
        import win32com.client
    except ImportError:
        return False

    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    word.DisplayAlerts = 0
    document = None
    try:
        document = word.Documents.Open(
            str(docx_path),
            ReadOnly=True,
            AddToRecentFiles=False,
            Visible=False,
        )
        document.ExportAsFixedFormat(str(pdf_path), 17)
    finally:
        if document is not None:
            document.Close(False)
        word.Quit()
    return pdf_path.exists()


def _convert_with_libreoffice(docx_path: Path, output_dir: Path) -> Path | None:
    soffice = _find_libreoffice()
    if not soffice:
        return None

    env = os.environ.copy()
    env.setdefault("HOME", str(output_dir.parent))
    subprocess.run(
        [
            soffice,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(docx_path),
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    pdf_path = output_dir / f"{docx_path.stem}.pdf"
    return pdf_path if pdf_path.exists() else None


def render_docx(docx_path: Path, output_dir: Path | None = None) -> dict[str, object]:
    docx_path = docx_path.resolve()
    if not docx_path.exists():
        raise FileNotFoundError(f"DOCX file not found: {docx_path}")

    output_dir = (output_dir or docx_path.parent / "render").resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = output_dir / f"{docx_path.stem}.pdf"

    converted = _convert_with_word(docx_path, pdf_path)
    if not converted:
        converted_pdf = _convert_with_libreoffice(docx_path, output_dir)
        if converted_pdf is None:
            raise RuntimeError(
                "No DOCX renderer is available. Install Microsoft Word on Windows "
                "or LibreOffice (`soffice`) on another platform."
            )
        pdf_path = converted_pdf

    try:
        import fitz
    except ImportError as exc:
        raise RuntimeError("PyMuPDF is required to render PDF pages. Install `pymupdf`.") from exc

    pdf = fitz.open(pdf_path)
    pages: list[dict[str, object]] = []
    try:
        for index, page in enumerate(pdf, start=1):
            pix = page.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), alpha=False)
            image_path = output_dir / f"page-{index}.png"
            pix.save(image_path)
            pages.append(
                {
                    "page": index,
                    "path": str(image_path),
                    "width": pix.width,
                    "height": pix.height,
                }
            )
    finally:
        pdf.close()

    return {
        "docx": str(docx_path),
        "pdf": str(pdf_path),
        "page_count": len(pages),
        "pages": pages,
    }
