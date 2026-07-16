import sqlite3

conn = sqlite3.connect('dev.db')
c = conn.cursor()

c.execute("SELECT count(*), revision_comment FROM ntin_products WHERE status='revision' GROUP BY revision_comment ORDER BY count(*) DESC LIMIT 10")
for count, comment in c.fetchall():
    print(f"[{count}] {comment}")

