import os
import glob

html_files = glob.glob(r'c:\Users\user\Desktop\retailpool\frontend\*.html')

for file_path in html_files:
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Do the replacements
    new_content = content.replace('href="#" data-i="footer_l_privacy"', 'href="privacy.html" data-i="footer_l_privacy"')
    new_content = new_content.replace('href="#" data-i="footer_l_terms"', 'href="terms.html" data-i="footer_l_terms"')
    new_content = new_content.replace('href="#" data-i="footer_l_offer"', 'href="terms.html" data-i="footer_l_offer"')
    new_content = new_content.replace('href="https://t.me/@Lulsiok"', 'href="https://t.me/Lulsiok"')
    
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"Updated {file_path}")
print("Done.")
