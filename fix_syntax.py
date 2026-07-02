import re
with open("retailpool/routers/ntin.py", "r", encoding="utf-8") as f:
    content = f.read()

# find lines starting with "async def " that don't end with ":"
def fix_colon(match):
    line = match.group(0)
    if not line.strip().endswith(":"):
        return line + ":"
    return line

content = re.sub(r'^async def .*$', fix_colon, content, flags=re.MULTILINE)

with open("retailpool/routers/ntin.py", "w", encoding="utf-8") as f:
    f.write(content)
