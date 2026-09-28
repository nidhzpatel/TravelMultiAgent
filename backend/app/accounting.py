"""Cost aggregation shared by initial plans and edits; never modifies USD prices."""
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def recompute_costs(data: dict) -> dict:
    def amount(value):
        try:
            result = Decimal(str(value))
        except (InvalidOperation, ValueError):
            raise ValueError("Invalid cost") from None
        if not result.is_finite() or result < 0:
            raise ValueError("Costs must be finite and nonnegative")
        return result

    def rounded(value):
        return float(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))

    rate = amount(data.get("exchange_rate", 1))
    if rate <= 0:
        raise ValueError("Exchange rate must be positive")
    subtotal = Decimal(0)
    unknown = False
    for day in data.get("days", []):
        totals = {}
        for category, items in (
            ("transit", day.get("transit_legs") or []),
            ("activity", day.get("activities") or []),
            ("stay", [day["stay"]] if day.get("stay") else []),
        ):
            cost = Decimal(0)
            for item in items:
                value = item.get("estimated_cost_usd")
                if value is None:
                    unknown = True
                    continue
                value = amount(value)
                cost += value
                # Activity display prices remain hidden; USD evidence remains intact.
                item["estimated_cost"] = None if category == "activity" else rounded(value * rate)
            totals[category] = cost
            day[f"daily_{category}_cost_usd"] = rounded(cost)
            day[f"daily_{category}_cost"] = rounded(cost * rate)
        daily = sum(totals.values(), Decimal(0))
        day["total_daily_cost_usd"] = rounded(daily)
        day["total_daily_cost"] = rounded(daily * rate)
        subtotal += daily
    cab = data.get("cab_service")
    if cab:
        value = amount(cab.get("estimated_cost_usd"))
        cab["estimated_cost"] = rounded(value * rate)
        subtotal += value
    # Retain the initial planner's documented 10% contingency policy.
    total = subtotal * Decimal("1.10")
    data["actual_calculated_cost_usd"] = rounded(total)
    data["actual_calculated_cost"] = rounded(total * rate)
    notes = data.setdefault("notes", [])
    # Replace derived notices so repeated edits do not retain obsolete shortfalls.
    notes[:] = [n for n in notes if not n.startswith(("Estimated cost exceeds your budget", "Some item costs are unknown", "A 10% contingency"))]
    notes.append("A 10% contingency buffer has been added to the known item costs.")
    if unknown:
        notes.append("Some item costs are unknown. The total covers known costs only and does not establish budget feasibility.")
    budget = amount(data.get("total_budget_usd", 0))
    if budget and total > budget:
        notes.append(f"Estimated cost exceeds your budget by {rounded((total - budget) * rate):,.2f} {data.get('currency', 'USD')}. Change trip options or budget; prices have not been reduced.")
    return data
