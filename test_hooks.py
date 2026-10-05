import asyncio
from hooks import pre_hook, post_hook

ORDERS = {
    "O-1001": {"order_id": "O-1001", "amount_paid": 400, "amount_refunded": 0},
    "O-1004": {"order_id": "O-1004", "amount_paid": 1500, "amount_refunded": 1500},
    "O-1007": {"order_id": "O-1007", "amount_paid": 8000, "amount_refunded": 0},
}


async def fake_fetch(order_id):
    return ORDERS.get(order_id, {"error": "not found"})


cases = [
    ("get_order", {"order_id": "1001"}),
    ("get_order", {"order_id": "O-9999"}),
    ("get_order", {"order_id": "O-1001"}),
    ("issue_refund", {"order_id": "O-1001", "amount": 0, "reason": "x"}),
    ("issue_refund", {"order_id": "O-1004", "amount": 100, "reason": "damaged"}),
    ("issue_refund", {"order_id": "O-1001", "amount": 500, "reason": "damaged"}),
    ("issue_refund", {"order_id": "O-1001", "amount": 400, "reason": ""}),
    ("issue_refund", {"order_id": "O-1007", "amount": 8000, "reason": "bad"}),
    ("issue_refund", {"order_id": "O-1007", "amount": 8000, "reason": "Screen cracked on arrival"}),
]


async def main():
    print("--- PRE-HOOK ---")
    for name, args in cases:
        error, _ = await pre_hook(name, args, fake_fetch)
        print(name, args, "->", error or "OK")

    print("\n--- POST-HOOK ---")
    ctx = {"order": {"amount_refunded": 0}}
    args = {"order_id": "O-1001", "amount": 400}

    async def after_ok(order_id):
        return {"amount_refunded": 400}

    async def after_bad(order_id):
        return {"amount_refunded": 0}

    print(await post_hook("issue_refund", args, '{"status": "refunded"}', ctx, after_ok))
    print(await post_hook("issue_refund", args, '{"status": "refunded"}', ctx, after_bad))
    print(await post_hook("get_order", args, "plain text", ctx, after_ok))


asyncio.run(main())