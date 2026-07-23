import os
import re
import sys

with open('index.html', encoding='utf-8') as f:
    content = f.read()

nav_match = re.search(r'<nav id="mainNav">.*?</nav>', content, re.DOTALL)
footer_match = re.search(r'<footer>.*?</footer>', content, re.DOTALL)

if not nav_match or not footer_match:
    print('Could not find nav or footer in index.html')
    sys.exit(1)

nav_html = nav_match.group(0)
footer_html = footer_match.group(0)

html_files = [f for f in os.listdir('.') if f.endswith('.html') and f != 'index.html']

for filename in html_files:
    with open(filename, encoding='utf-8') as f:
        file_content = f.read()
    
    # Replace old nav
    file_content = re.sub(r'<nav>.*?</nav>', nav_html, file_content, flags=re.DOTALL)
    file_content = re.sub(r'<nav id="mainNav">.*?</nav>', nav_html, file_content, flags=re.DOTALL)
    
    # Inject active class into the nav based on filename
    file_content = file_content.replace(
        f'<a href="{filename}"', 
        f'<a href="{filename}" class="active"'
    )
    
    # Replace old footer
    file_content = re.sub(r'<footer>.*?</footer>', footer_html, file_content, flags=re.DOTALL)
    
    with open(filename, 'w', encoding='utf-8') as f:
        f.write(file_content)

print(f'Updated {len(html_files)} HTML files with new nav and footer.')
