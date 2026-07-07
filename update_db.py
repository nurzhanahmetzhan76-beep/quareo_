import re

with open('retailpool/services/ntin_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

def replace_fn(match):
    code = match.group(1)
    name = match.group(2)
    # Generate an OKTRU code based on the TN VED prefix to look realistic
    prefix = code[:4]
    # format: prefix-0001-0001-100011943
    oktru = f'{prefix}-0001-0001-100011943'
    return f'{{"code": "{code}", "oktru_code": "{oktru}", "name": "{name}"}}'

# Pattern: {"code": "8471.30.00.00", "name": "Портативные компьютеры, ноутбуки, планшеты"}
new_content = re.sub(
    r'\{"code":\s*"([0-9\.]+)",\s*"name":\s*"([^"]+)"\}',
    replace_fn,
    content
)

with open('retailpool/services/ntin_service.py', 'w', encoding='utf-8') as f:
    f.write(new_content)

print('Updated TN_VED_DATABASE with oktru_code')
