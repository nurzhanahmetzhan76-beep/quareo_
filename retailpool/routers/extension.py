"""
Extension Router — endpoints for Chrome Extension distribution.
"""

import io
import os
import zipfile
from pathlib import Path

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/api/extension", tags=["Extension"])


@router.get("/download")
async def download_extension():
    """
    Zips the chrome_extension directory on the fly and returns it as a download.
    Public endpoint — no auth required.
    """
    # Path to the extension directory
    base_dir = Path(__file__).resolve().parent.parent.parent
    ext_dir = base_dir / "chrome_extension"

    if not ext_dir.exists() or not ext_dir.is_dir():
        raise HTTPException(status_code=404, detail="Extension directory not found")

    # Create a zip archive in memory
    zip_buffer = io.BytesIO()
    
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(ext_dir):
            for file in files:
                file_path = Path(root) / file
                arcname = file_path.relative_to(ext_dir)
                zip_file.write(file_path, arcname)

    zip_buffer.seek(0)

    headers = {
        "Content-Disposition": 'attachment; filename="quareo_extension.zip"'
    }
    
    return StreamingResponse(
        zip_buffer, 
        media_type="application/zip", 
        headers=headers
    )
