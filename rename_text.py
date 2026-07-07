import os
import re

directories_to_scan = ['.']
extensions = {'.py', '.js', '.css', '.html', '.md', '.yml', '.yaml', '.txt'}
exclude_dirs = {'.venv', '.git', '__pycache__', 'alembic', 'node_modules', '.pytest_cache'}

def process_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
            
        new_content = content.replace("RetailPool AI", "Quareo")
        new_content = new_content.replace("RetailPool", "Quareo")
        new_content = new_content.replace("Retailpool AI", "Quareo")
        new_content = new_content.replace("Retailpool", "Quareo")
        
        # Don't replace 'retailpool' (lowercase) because it's the package name!
        
        if new_content != content:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated: {filepath}")
    except Exception as e:
        print(f"Error processing {filepath}: {e}")

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in exclude_dirs]
    for file in files:
        if any(file.endswith(ext) for ext in extensions):
            process_file(os.path.join(root, file))
