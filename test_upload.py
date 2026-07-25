import asyncio
import io
import os
import openpyxl
from fastapi import UploadFile
from sqlalchemy import select
from retailpool.database import async_session_maker
from retailpool.models.user import User
from retailpool.routers.repricing import upload_sync

async def main():
    async with async_session_maker() as db:
        # Get first user
        user = (await db.execute(select(User).limit(1))).scalar_one_or_none()
        if not user:
            print("No user found")
            return
        
        # Create a dummy excel file in memory
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["SKU", "Price", "Name"])
        ws.append(["12345", 1000, "Test Product"])
        
        # Save to bytes
        excel_bytes = io.BytesIO()
        wb.save(excel_bytes)
        excel_bytes.seek(0)
        
        # Create UploadFile
        upload_file = UploadFile(filename="test.xlsx", file=excel_bytes)
        
        try:
            res = await upload_sync(file=upload_file, current_user=user, db=db)
            print("Success:", res)
        except Exception as e:
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
