"""Quick test for the repricing decision engine."""
from retailpool.services.repricing_service import compute_new_price

tests = [
    # (my_price, min_price, base_price, step, comp_price) -> expected
    (50000, 40000, 50000, 5, 49000, 48995, "undercut"),
    (41000, 40000, 50000, 5, 40003, 40000, "floor_hit"),
    (40000, 40000, 50000, 5, 39000, None, "alert_only"),
    (48000, 40000, 50000, 5, 55000, 50000, "raise_back"),
    (48000, 40000, None, 5, 55000, 54995, "raise_back"),
    (50000, 40000, 50000, 10, 49000, 48995, "undercut"),  # step capped
    (48995, 40000, 50000, 5, 49000, None, "no_change"),
]

for i, (my, mn, base, step, comp, exp_price, exp_action) in enumerate(tests, 1):
    price, action = compute_new_price(my, mn, base, step, comp)
    ok = price == exp_price and action == exp_action
    status = "PASS" if ok else "FAIL"
    print(f"Test {i}: {status} | got ({price}, {action}) expected ({exp_price}, {exp_action})")

print("\nDone!")
