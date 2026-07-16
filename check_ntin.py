import sqlite3

conn = sqlite3.connect('dev.db')
c = conn.cursor()

c.execute("SELECT count(*), status FROM ntin_products GROUP BY status")
print("NTIN products by status:", c.fetchall())

# Check how many lack a TN VED code (tn_ved_code)
c.execute("SELECT count(*), status FROM ntin_products WHERE tn_ved_code IS NULL OR tn_ved_code = '' GROUP BY status")
print("Missing TN VED by status:", c.fetchall())

# Check a few rows from draft without tn ved
c.execute("SELECT id, title_ru, tn_ved_code, oktru_code FROM ntin_products WHERE status='draft' AND (tn_ved_code IS NULL OR tn_ved_code = '') LIMIT 3")
print("Sample missing TN VED:", c.fetchall())

