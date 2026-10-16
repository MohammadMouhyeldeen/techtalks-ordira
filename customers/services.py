from decimal import Decimal

from orders.models import Order


def outstanding_orders(customer):
    """Orders counting toward a customer's outstanding balance.

    An order counts when it has no recorded payment yet and isn't
    cancelled. Payment is only ever recorded as PAID, in full — partial
    payments are out of scope for the MVP — so "has a payment row" and
    "is paid" are the same thing today, and payment__isnull=True is a
    single query rather than a Python loop checking each order."""
    return (
        customer.orders
        .exclude(status=Order.Status.CANCELLED)
        .filter(payment__isnull=True)
        .order_by("-created_at")
    )


def outstanding_balances(orders):
    """Sums order.total per currency — never mixes currencies into one
    number, since a USD amount and an LBP amount can't be meaningfully
    added. Returns {} when there's nothing outstanding."""
    balances = {}

    for order in orders:
        balances[order.currency] = (
            balances.get(order.currency, Decimal("0.00")) + order.total
        )

    return balances
