import asyncio
import csv
import sys
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import delete
from retailpool.models.ntin import OktruDictionary
from retailpool.database import async_session_factory

async def main(file_path):
    print(f"Loading data from {file_path}...")
    
    records = []
    if file_path.endswith('.csv'):
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            headers = next(reader)
            for row in reader:
                if len(row) >= 2:
                    code, name = row[0].strip(), row[1].strip()
                    if code and name:
                        records.append({"code": code, "name_ru": name, "level": 1})
    elif file_path.endswith('.xlsx'):
        import openpyxl
        wb = openpyxl.load_workbook(file_path, data_only=True)
        sheet = wb.active
        
        # Determine columns dynamically if possible
        headers = [str(c.value).lower() if c.value else "" for c in sheet[1]]
        code_idx, name_idx = 0, 1
        for i, h in enumerate(headers):
            if "код" in h or "oktru" in h or "октру" in h: code_idx = i
            if "наименование" in h or "описание" in h or "название" in h: name_idx = i
            
        for row in sheet.iter_rows(min_row=2, values_only=True):
            if row and len(row) > max(code_idx, name_idx):
                code = str(row[code_idx]).strip() if row[code_idx] else ""
                name = str(row[name_idx]).strip() if row[name_idx] else ""
                if code and name and code != "None":
                    records.append({"code": code, "name_ru": name, "level": 1})
    else:
        print("Unsupported file format. Use .csv or .xlsx")
        return

    if not records:
        print("No valid records found.")
        return

    print(f"Found {len(records)} records. Connecting to DB...")
    
    async with async_session_factory() as session:
        async with session.begin():
            print("Clearing existing OKTRU dictionary...")
            await session.execute(delete(OktruDictionary))
            
            print(f"Inserting {len(records)} records...")
            chunk_size = 1000
            for i in range(0, len(records), chunk_size):
                chunk = records[i:i+chunk_size]
                objs = [OktruDictionary(**r) for r in chunk]
                session.add_all(objs)
            
    print("Done! OKTRU dictionary updated successfully.")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python import_oktru.py <path_to_excel_or_csv_file>")
        sys.exit(1)
    asyncio.run(main(sys.argv[1]))
