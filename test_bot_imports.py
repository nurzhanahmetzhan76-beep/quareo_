"""Quick smoke test to verify bot module imports work correctly."""

import sys
sys.path.insert(0, ".")

errors = []


def test_import(label, fn):
    try:
        fn()
        print(f"  [OK] {label}")
    except Exception as e:
        print(f"  [FAIL] {label}: {e}")
        errors.append(label)


print("=" * 50)
print("RetailPool AI — Bot Import Verification")
print("=" * 50)

# 1. Config
test_import("bot.config", lambda: __import__("retailpool.bot.config"))

# 2. Keyboards
test_import("bot.keyboards", lambda: __import__("retailpool.bot.keyboards"))

# 3. API Client
test_import("bot.api_client", lambda: __import__("retailpool.bot.api_client"))

# 4. PDF Generator
test_import("bot.pdf_generator", lambda: __import__("retailpool.bot.pdf_generator"))

# 5. Handlers
test_import("bot.handlers.start", lambda: __import__("retailpool.bot.handlers.start"))
test_import("bot.handlers.pools", lambda: __import__("retailpool.bot.handlers.pools"))
test_import("bot.handlers.scanner", lambda: __import__("retailpool.bot.handlers.scanner"))
test_import("bot.handlers.documents", lambda: __import__("retailpool.bot.handlers.documents"))
test_import("bot.handlers.alerts", lambda: __import__("retailpool.bot.handlers.alerts"))

# 6. Alert Worker
test_import("bot.alert_worker", lambda: __import__("retailpool.bot.alert_worker"))

# 7. Models
test_import("bot.models", lambda: __import__("retailpool.bot.models"))

# 8. App
test_import("bot.app", lambda: __import__("retailpool.bot.app"))

print()
if errors:
    print(f"FAILED: {len(errors)} module(s) had import errors:")
    for e in errors:
        print(f"  - {e}")
    sys.exit(1)
else:
    print("ALL IMPORTS PASSED! Bot is ready to start.")
    print()
    print("To run the bot:")
    print("  .venv\\Scripts\\python.exe run_bot.py --polling")
    sys.exit(0)
