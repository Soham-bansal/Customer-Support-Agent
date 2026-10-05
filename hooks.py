import json
import re

ORDER_ID_PATTERN = re.compile(r"^O-\d{4}$")
LONG_REFUND_THRESHOLD = 5000
MIN_REASON_LENGTH = 10


def _error(message: str) -> dict:
    return {"status": 400, "error": message}

async def pre_hook(name, args, fetch_order):
    """Check a tool request BEFORE it runs. Returns (error, context).
    error is a dict if the request is bad, otherwise None."""
    order = None
    order_id = args.get("order_id")

    if order_id is not None:
        if not ORDER_ID_PATTERN.match(order_id):
            return _error(
                f"Invalid order ID '{order_id}'. Expected format O-1234 "
                "(letter O, a dash, then 4 digits)."
            ), {}
        order = await fetch_order(order_id)
        if "error" in order:
            return _error(f"Order {order_id} does not exist."), {}

    if name == "issue_refund":
        if order is None:
            return _error("order_id is required for a refund."), {}
        amount = args.get("amount")
        if amount is None or amount <= 0:
            return _error("Refund amount must be greater than 0."), {}

        refundable = order["amount_paid"] - order["amount_refunded"]
        if refundable <= 0:
            return _error(f"Order {order_id} is already fully refunded."), {}
        if amount > refundable:
            return _error(
                f"Refund amount ₹{amount} is more than the refundable balance of ₹{refundable}."
            ), {}

        reason = (args.get("reason") or "").strip()
        if not reason:
            return _error("A reason is required for every refund."), {}
        if amount > LONG_REFUND_THRESHOLD and len(reason) < MIN_REASON_LENGTH:
            return _error(
                f"Refunds over ₹{LONG_REFUND_THRESHOLD} need a written reason "
                f"of at least {MIN_REASON_LENGTH} characters."
            ), {}

    return None, {"order": order}


async def post_hook(name, args, result_text, context, fetch_order):
    """Check the result AFTER a tool ran. Returns the text to give the LLM."""
    if name != "issue_refund":
        return result_text

    before = context["order"]
    after = await fetch_order(args["order_id"])
    expected = before["amount_refunded"] + args["amount"]

    if abs(after.get("amount_refunded", -1) - expected) > 0.01:
        return json.dumps(
            {
                "status": "post_check_failed",
                "error": "The refund could not be confirmed. Do NOT retry it and "
                "do NOT tell the customer it succeeded. Flag the order for review "
                "and report that the refund status is unconfirmed."
                ,
            },
            ensure_ascii=False,
        )

    result = json.loads(result_text)
    result["verified"] = True
    return json.dumps(result, ensure_ascii=False)



APPROVAL_THRESHOLD = 500


def approval_decision(args: dict, eligibility: dict) -> dict:
    """Decide what should happen before an issue_refund call runs.
    Returns {"action": "block" | "approve" | "auto", "reason": str}."""
    decision = eligibility.get("decision")
    amount = args["amount"]

    if decision not in ("eligible", "borderline"):
        return {
            "action": "block",
            "reason": eligibility.get("reason", "Eligibility could not be confirmed"),
        }

    if amount >= APPROVAL_THRESHOLD:
        return {
            "action": "approve",
            "reason": f"Refund of ₹{amount} is ₹{APPROVAL_THRESHOLD} or more",
        }

    if decision == "borderline":
        return {
            "action": "approve",
            "reason": "Order is slightly past the return window",
        }

    return {
        "action": "auto",
        "reason": "Within the return window and under the approval threshold",
    }