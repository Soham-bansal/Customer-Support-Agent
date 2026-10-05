import json
from pathlib import Path
import sys

DATA_DIR = Path(__file__).parent / "data"

# helper function to load JSON data 
def _load(filename):
    with open(DATA_DIR / filename, encoding="utf-8") as f:
        return json.load(f)
# helper function to save JSON data
def _save(filename, data):
    with open(DATA_DIR / filename, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def get_order(order_id: str) -> dict:
    """Get the full details of one order: customer, category, items, amount paid,
    amount already refunded, status, and days since delivery."""
    for order in _load("orders.json"):
        if order["order_id"] == order_id:
            return order
    return {"error": f"Order {order_id} not found"}


def get_customer_orders(customer_id: str) -> list:
    """Get all orders of a customer, including refund history. Use this to review a
    customer or count how many refunds they had recently."""
    orders = [o for o in _load("orders.json") if o["customer_id"] == customer_id]
    if not orders:
        return [{"error": f"Customer {customer_id} not found"}]
    return orders

def get_tracking(order_id: str) -> dict:
    """Get the shipping and delivery status of an order."""
    order = get_order(order_id)
    if "error" in order:
        return order
    return {
        "order_id": order_id,
        "status": order["status"],
        "tracking": order["tracking"],
    }

def get_pending_refund_requests() -> list:
    """Get the open refund tickets that still need to be processed."""
    return [t for t in _load("refund_requests.json") if t["status"] == "open"]



RETURN_WINDOWS = {"Electronics": 15, "Clothing": 30, "Other": 30}
BORDERLINE_DAYS = 2
REPEAT_REFUND_LIMIT = 3
REPEAT_REFUND_DAYS = 90


def _recent_refund_count(customer_id: str) -> int:
    orders = [o for o in _load("orders.json") if o["customer_id"] == customer_id]
    return sum(
        1
        for o in orders
        if o["refunded_days_ago"] is not None
        and o["refunded_days_ago"] <= REPEAT_REFUND_DAYS
    )

def check_refund_eligibility(order_id: str) -> dict:
    """Check whether an order can be refunded under the shop rules. Returns a
    decision (eligible, borderline, flag, or not_eligible), the reason, and the
    maximum refundable amount."""
    order = get_order(order_id)
    if "error" in order:
        return order

    result = {
        "order_id": order_id,
        "refundable_amount": order["amount_paid"] - order["amount_refunded"],
        "days_since_delivery": order["delivered_days_ago"],
        "window_days": RETURN_WINDOWS[order["category"]],
        "recent_refunds_90d": _recent_refund_count(order["customer_id"]),
    }

    if order["status"] == "cancelled":
        result.update(decision="not_eligible", reason="Order was cancelled")
    elif order["status"] != "delivered":
        result.update(decision="not_eligible", reason="Order has not been delivered yet")
    elif result["refundable_amount"] <= 0:
        result.update(decision="not_eligible", reason="Order was already fully refunded")
    elif result["recent_refunds_90d"] >= REPEAT_REFUND_LIMIT:
        result.update(decision="flag", reason="Customer has 3 or more refunds in the last 90 days")
    elif result["days_since_delivery"] <= result["window_days"]:
        result.update(decision="eligible", reason="Within the return window")
    elif result["days_since_delivery"] <= result["window_days"] + BORDERLINE_DAYS:
        result.update(decision="borderline", reason="Slightly past the return window")
    else:
        result.update(decision="not_eligible", reason="Past the return window")

    return result



def issue_refund(order_id: str, amount: float, reason: str) -> dict:
    """Issue a full or partial refund for an order. This moves money, so it is a
    risky action. Needs the order ID, the amount to refund, and a reason."""
    orders = _load("orders.json")
    for order in orders:
        if order["order_id"] == order_id:
            order["amount_refunded"] += amount
            order["refunded_days_ago"] = 0
            _save("orders.json", orders)
            return {"status": "refunded", "order_id": order_id, "amount": amount, "reason": reason}
    return {"error": f"Order {order_id} not found"}


def flag_for_review(order_id: str, reason: str) -> dict:
    """Flag an order for manual review by a human instead of refunding it."""
    path = DATA_DIR / "flagged_cases.json"
    flagged = json.loads(path.read_text(encoding="utf-8")) if path.exists() else []
    flagged.append({"order_id": order_id, "reason": reason})
    path.write_text(json.dumps(flagged, indent=2), encoding="utf-8")
    return {"status": "flagged", "order_id": order_id, "reason": reason}


def send_email(email: str, subject: str, message: str) -> dict:
    """Send an email to a customer (simulated, it prints to the console)."""
    print(f"\n--- EMAIL to {email} ---\nSubject: {subject}\n{message}\n", file=sys.stderr)
    return {"status": "sent", "to": email, "subject": subject}
