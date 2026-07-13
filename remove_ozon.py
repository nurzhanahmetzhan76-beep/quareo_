import glob
import re
import os

def remove_ozon_link():
    files = glob.glob('frontend/*.html')
    for f in files:
        try:
            with open(f, 'r', encoding='utf-8') as file:
                content = file.read()
            
            # The exact line that was injected
            pattern1 = r'\n\s*<a href="ozon_scanner\.html"[^>]*>Сканер Ozon</a>'
            
            new_content = re.sub(pattern1, '', content)
            
            if new_content != content:
                with open(f, 'w', encoding='utf-8') as file:
                    file.write(new_content)
                print(f"Removed from {f}")
        except Exception as e:
            print(f"Error processing {f}: {e}")

remove_ozon_link()
