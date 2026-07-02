import re

with open("retailpool/routers/ntin.py", "r", encoding="utf-8") as f:
    content = f.read()

# For every function definition starting with @router
def replacer(match):
    decorator = match.group(1)
    func_def = match.group(2)
    # add current_user: User = Depends(get_current_user)
    if "current_user" in func_def:
        return match.group(0) # already patched
    
    if func_def.endswith("()"):
        new_def = func_def[:-1] + "current_user: User = Depends(get_current_user))"
    else:
        new_def = func_def[:-1] + ", current_user: User = Depends(get_current_user))"
        
    return f"{decorator}\n{new_def}"

content = re.sub(r'(@router\.[^\n]+)\n(async def [^\(]+\([^\)]*\)):', replacer, content)

# Replace DEMO_USER_ID with current_user.id
content = content.replace("DEMO_USER_ID", "current_user.id")

with open("retailpool/routers/ntin.py", "w", encoding="utf-8") as f:
    f.write(content)

print("Patched ntin.py")
