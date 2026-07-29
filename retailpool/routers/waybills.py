"""Waybill PDF processing and Smart Print archive tracking."""

from __future__ import annotations

import hashlib
import io
import logging
import re
import zipfile
from datetime import datetime
from pathlib import PurePosixPath
from typing import Any

import fitz  # PyMuPDF
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pypdf import PageObject, PdfReader, PdfWriter, Transformation
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from retailpool.database import get_db
from retailpool.models.user import User
from retailpool.models.waybill import ProcessedWaybill, WaybillUploadHistory
from retailpool.services.auth_service import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/waybills", tags=["Waybills"])

A4_WIDTH = 595.276
A4_HEIGHT = 842.0
MAX_UPLOAD_SIZE = 50 * 1024 * 1024
_NUMBER_RE = re.compile(r"(?<!\d)(\d{3,})(?!\d)")
_IDENTIFIED_NUMBER_RE = re.compile(
    r"(?:order|waybill|invoice|shipment|\u0437\u0430\u043a\u0430\u0437|"
    r"\u043d\u0430\u043a\u043b\u0430\u0434\u043d)[^\d]{0,24}(\d{3,})",
    re.IGNORECASE,
)


def _validate_waybill_access(current_user: User) -> None:
    """Keep the existing subscription rules shared by analyse and print requests."""
    user_plan = (current_user.plan or "free").lower()
    plan_limits = {
        "free": 1,
        "\u043d\u0430\u043a\u043b\u0430\u0434\u043d\u044b\u0435": 999999,
        "waybills": 999999,
        "start": 999999,
        "\u0441\u0442\u0430\u0440\u0442": 999999,
        "business": 999999,
        "\u0431\u0438\u0437\u043d\u0435\u0441": 999999,
        "unlimited": 999999,
        "\u0431\u0435\u0437\u043b\u0438\u043c\u0438\u0442": 999999,
        "\u0430\u0433\u0435\u043d\u0442\u0441\u0442\u0432\u043e": 999999,
    }

    if user_plan not in plan_limits and current_user.email != "karimbai.ali10@mail.ru":
        raise HTTPException(status_code=403, detail="Waybills are not available for this plan.")


def _validate_print_limit(current_user: User) -> None:
    """Retain the former generation limit; archive analysis never consumes it."""
    user_plan = (current_user.plan or "free").lower()
    plan_limits = {
        "free": 1,
        "\u043d\u0430\u043a\u043b\u0430\u0434\u043d\u044b\u0435": 999999,
        "waybills": 999999,
        "start": 999999,
        "\u0441\u0442\u0430\u0440\u0442": 999999,
        "business": 999999,
        "\u0431\u0438\u0437\u043d\u0435\u0441": 999999,
        "unlimited": 999999,
        "\u0431\u0435\u0437\u043b\u0438\u043c\u0438\u0442": 999999,
        "\u0430\u0433\u0435\u043d\u0442\u0441\u0442\u0432\u043e": 999999,
    }
    limit = plan_limits.get(user_plan, 0)
    if getattr(current_user, "waybills_used", 0) >= limit and current_user.email != "karimbai.ali10@mail.ru":
        if user_plan == "free":
            raise HTTPException(status_code=403, detail="The free waybill generation limit has been used.")
        raise HTTPException(status_code=403, detail="The waybill generation limit for this plan has been used.")


async def _read_upload(file: UploadFile) -> bytes:
    filename = file.filename or ""
    if not filename.lower().endswith(".zip"):
        raise HTTPException(status_code=400, detail="Please upload a ZIP archive.")
    zip_data = await file.read()
    if len(zip_data) > MAX_UPLOAD_SIZE:
        raise HTTPException(status_code=400, detail="The archive is too large (maximum 50 MB).")
    return zip_data


def _numeric_identifier(value: str) -> str | None:
    """Prefer an explicitly labelled order/waybill number, then the longest number."""
    explicit = _IDENTIFIED_NUMBER_RE.search(value)
    if explicit:
        return explicit.group(1)
    numbers = _NUMBER_RE.findall(value)
    if not numbers:
        return None
    return max(enumerate(numbers), key=lambda item: (len(item[1]), -item[0]))[1]


def extract_waybill_identifier(pdf_name: str, pdf_bytes: bytes) -> str:
    """Return a stable identifier without retaining a PDF or its full text.

    Kaspi archives normally put the order number in the filename.  If it is
    absent, a labelled number in the document is used.  A content digest is a
    deterministic final fallback, so unlabelled documents are still safe from
    repeated printing.
    """
    normalised_name = PurePosixPath(pdf_name.replace("\\", "/")).stem
    number = _numeric_identifier(normalised_name)
    if number:
        return f"order:{number}"

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
        text = " ".join(page.get_text("text") or "" for page in document)
        document.close()
        number = _numeric_identifier(re.sub(r"\s+", " ", text))
        if number:
            return f"document:{number}"
    except Exception as exc:  # The content digest below remains a safe fallback.
        logger.warning("Could not extract waybill ID from %s: %s", pdf_name, exc)

    return f"content:{hashlib.sha256(pdf_bytes).hexdigest()}"


def _order_time_key(pdf_name: str, waybill_id: str) -> int:
    """Use the order number as the same arrival-order proxy used previously."""
    number = _numeric_identifier(pdf_name) or _numeric_identifier(waybill_id)
    return int(number) if number else 999999999999999999


def _read_archive(zip_data: bytes) -> list[dict[str, Any]]:
    try:
        with zipfile.ZipFile(io.BytesIO(zip_data)) as archive:
            pdf_names = [name for name in archive.namelist() if name.lower().endswith(".pdf")]
            if not pdf_names:
                raise HTTPException(status_code=400, detail="The ZIP archive does not contain PDF waybills.")

            files: list[dict[str, Any]] = []
            for index, pdf_name in enumerate(pdf_names):
                pdf_bytes = archive.read(pdf_name)
                identifier = extract_waybill_identifier(pdf_name, pdf_bytes)
                files.append(
                    {
                        "name": pdf_name,
                        "bytes": pdf_bytes,
                        "waybill_id": identifier,
                        "order_time": _order_time_key(pdf_name, identifier),
                        "original_index": index,
                    }
                )
            return files
    except zipfile.BadZipFile as exc:
        raise HTTPException(status_code=400, detail="The ZIP archive is invalid. Please download it again from Kaspi.") from exc


async def _processed_ids(db: AsyncSession, user_id: Any, identifiers: set[str]) -> set[str]:
    """Read in small chunks so large Kaspi archives also work on SQLite."""
    if not identifiers:
        return set()

    found: set[str] = set()
    values = list(identifiers)
    for start in range(0, len(values), 500):
        result = await db.scalars(
            select(ProcessedWaybill.waybill_id).where(
                ProcessedWaybill.user_id == user_id,
                ProcessedWaybill.waybill_id.in_(values[start:start + 500]),
            )
        )
        found.update(result.all())
    return found


def _split_new_waybills(
    files: list[dict[str, Any]], processed_ids: set[str]
) -> tuple[list[dict[str, Any]], int]:
    """Filter server-side before PDF merging, including duplicate files in one ZIP."""
    new_files: list[dict[str, Any]] = []
    already_processed = 0
    identifiers_in_archive: set[str] = set()
    for item in files:
        identifier = item["waybill_id"]
        if identifier in processed_ids or identifier in identifiers_in_archive:
            already_processed += 1
        else:
            new_files.append(item)
        identifiers_in_archive.add(identifier)
    return new_files, already_processed


def _build_pdf(files: list[dict[str, Any]], format: str) -> PdfWriter:
    """Existing PDF crop and merge mechanics, applied only to selected files."""
    writer = PdfWriter()
    all_pages = []

    for item in files:
        reader = PdfReader(io.BytesIO(item["bytes"]))
        for page in reader.pages:
            orig_w = float(page.mediabox.right - page.mediabox.left)
            if orig_w > 400:
                # Kaspi's A4 labels sit in the top-left quarter of the page.
                page.mediabox.upper_right = (297.638, 842.0)
                page.mediabox.lower_left = (0, 421.0)
                page.cropbox.upper_right = (297.638, 842.0)
                page.cropbox.lower_left = (0, 421.0)
                is_a4 = True
            else:
                is_a4 = False
            all_pages.append((page, is_a4))

    if format == "thermal":
        for page, is_a4 in all_pages:
            if is_a4:
                page.add_transformation(Transformation().translate(tx=0, ty=-421.0))
                page.mediabox.upper_right = (297.638, 421.0)
                page.mediabox.lower_left = (0, 0)
                page.cropbox.upper_right = (297.638, 421.0)
                page.cropbox.lower_left = (0, 0)
            writer.add_page(page)
    elif format == "a4":
        for index in range(0, len(all_pages), 4):
            chunk = all_pages[index:index + 4]
            merged_page = PageObject.create_blank_page(width=A4_WIDTH, height=A4_HEIGHT)
            if len(chunk) > 0:
                page, is_a4 = chunk[0]
                if not is_a4:
                    page.add_transformation(Transformation().translate(tx=0, ty=421.0))
                merged_page.merge_page(page)
            if len(chunk) > 1:
                page, is_a4 = chunk[1]
                if is_a4:
                    page.add_transformation(Transformation().translate(tx=297.638, ty=0))
                else:
                    page.add_transformation(Transformation().translate(tx=297.638, ty=421.0))
                merged_page.merge_page(page)
            if len(chunk) > 2:
                page, is_a4 = chunk[2]
                if is_a4:
                    page.add_transformation(Transformation().translate(tx=0, ty=-421.0))
                merged_page.merge_page(page)
            if len(chunk) > 3:
                page, is_a4 = chunk[3]
                if is_a4:
                    page.add_transformation(Transformation().translate(tx=297.638, ty=-421.0))
                else:
                    page.add_transformation(Transformation().translate(tx=297.638, ty=0))
                merged_page.merge_page(page)
            writer.add_page(merged_page)
    else:
        raise HTTPException(status_code=400, detail="Unknown print format.")
    return writer


@router.post("/analyze")
async def analyze_waybills(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Analyse an upload immediately and add one history item without storing PDFs."""
    _validate_waybill_access(current_user)
    files = _read_archive(await _read_upload(file))
    processed_ids = await _processed_ids(db, current_user.id, {item["waybill_id"] for item in files})
    new_files, already_processed = _split_new_waybills(files, processed_ids)

    db.add(
        WaybillUploadHistory(
            user_id=current_user.id,
            total_count=len(files),
            already_processed_count=already_processed,
            new_count=len(new_files),
        )
    )
    await db.flush()

    return {
        "total": len(files),
        "already_processed": already_processed,
        "new": len(new_files),
        "sort": "order_time_oldest_first",
    }


@router.get("/history")
async def get_waybill_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Return recent automatic archive-check results for the Smart Print timeline."""
    _validate_waybill_access(current_user)
    entries = await db.scalars(
        select(WaybillUploadHistory)
        .where(WaybillUploadHistory.user_id == current_user.id)
        .order_by(desc(WaybillUploadHistory.created_at))
        .limit(20)
    )
    return [
        {
            "total": entry.total_count,
            "already_processed": entry.already_processed_count,
            "new": entry.new_count,
            "created_at": entry.created_at.isoformat(),
        }
        for entry in entries
    ]


@router.post("/process")
async def process_waybills(
    file: UploadFile = File(...),
    format: str = Form(...),
    sort: str = Form("time"),
    smart_print: bool = Form(True),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Generate a PDF, excluding previously processed waybills by default.

    ``sort`` is retained for callers of the existing API but intentionally
    ignored: the only supported order is order-arrival time (oldest first).
    """
    del sort
    _validate_waybill_access(current_user)
    _validate_print_limit(current_user)

    files = _read_archive(await _read_upload(file))
    processed_ids = await _processed_ids(db, current_user.id, {item["waybill_id"] for item in files})
    new_files, already_processed = _split_new_waybills(files, processed_ids)
    files_to_print = new_files if smart_print else files

    if not files_to_print:
        raise HTTPException(status_code=409, detail="All waybills in this archive have already been processed.")

    files_to_print.sort(key=lambda item: (item["order_time"], item["original_index"]))
    try:
        writer = _build_pdf(files_to_print, format)
        out_pdf = io.BytesIO()
        writer.write(out_pdf)
        out_pdf.seek(0)
    except HTTPException:
        raise
    except Exception as exc:
        logger.exception("Waybill processing failed")
        raise HTTPException(status_code=500, detail=f"Waybill processing failed: {exc}") from exc

    # Only documents that had not been seen before become processed.  The PDF
    # bytes themselves are never saved.
    for item in new_files:
        db.add(
            ProcessedWaybill(
                user_id=current_user.id,
                waybill_id=item["waybill_id"],
                store_name=current_user.company_name,
            )
        )
    if current_user.email != "karimbai.ali10@mail.ru":
        current_user.waybills_used = getattr(current_user, "waybills_used", 0) + 1
    await db.flush()

    return StreamingResponse(
        out_pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=waybills_{format}.pdf",
            "Access-Control-Expose-Headers": "Content-Disposition, X-Waybills-Total, X-Waybills-Already-Processed, X-Waybills-New, X-Waybills-Printed",
            "X-Waybills-Total": str(len(files)),
            "X-Waybills-Already-Processed": str(already_processed),
            "X-Waybills-New": str(len(new_files)),
            "X-Waybills-Printed": str(len(files_to_print)),
        },
    )
