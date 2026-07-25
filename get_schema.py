import sqlite3
conn = sqlite3.connect('dev.db')
cursor = conn.cursor()

with open('schema_output.txt', 'w') as f:
    # Get all indices for repricing_rules
    indices = cursor.execute("PRAGMA index_list(repricing_rules)").fetchall()
    f.write(f"Indices: {indices}\n")
    for idx in indices:
        idx_name = idx[1]
        idx_info = cursor.execute(f"PRAGMA index_info('{idx_name}')").fetchall()
        f.write(f"Index {idx_name}: {idx_info}\n")
        
    # Get table info
    table_info = cursor.execute("PRAGMA table_info(repricing_rules)").fetchall()
    f.write(f"Table Info: {table_info}\n")

conn.close()
