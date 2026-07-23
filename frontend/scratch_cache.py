import os

html_files = [f for f in os.listdir('.') if f.endswith('.html')]

for filename in html_files:
    with open(filename, 'r', encoding='utf-8') as f:
        content = f.read()

    content = content.replace('assets/style.css"', 'assets/style.css?v=2"')
    content = content.replace('assets/dashboard.css"', 'assets/dashboard.css?v=2"')
    content = content.replace('assets/common.js"', 'assets/common.js?v=2"')

    with open(filename, 'w', encoding='utf-8') as f:
        f.write(content)

print('Updated cache busters.')
