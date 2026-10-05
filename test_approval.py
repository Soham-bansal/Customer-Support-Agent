from hooks import approval_decision

cases = [
    ("eligible, ₹400", {"amount": 400}, {"decision": "eligible"}),
    ("eligible, ₹499", {"amount": 499}, {"decision": "eligible"}),
    ("eligible, ₹500", {"amount": 500}, {"decision": "eligible"}),
    ("eligible, ₹2000", {"amount": 2000}, {"decision": "eligible"}),
    ("eligible, ₹8000", {"amount": 8000}, {"decision": "eligible"}),
    ("borderline, ₹300", {"amount": 300}, {"decision": "borderline"}),
    ("not_eligible, ₹100", {"amount": 100}, {"decision": "not_eligible", "reason": "Past the return window"}),
    ("flag, ₹100", {"amount": 100}, {"decision": "flag", "reason": "Too many recent refunds"}),
    ("no decision, ₹100", {"amount": 100}, {"error": "lookup failed"}),
]

for label, args, eligibility in cases:
    r = approval_decision(args, eligibility)
    print(f"{label:22} -> {r['action']:8} | {r['reason']}")