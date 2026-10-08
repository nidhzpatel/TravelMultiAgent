"""Deterministic native-currency budget ledger."""

from decimal import Decimal, ROUND_HALF_UP

from app.domain.contracts import Budget, BudgetBreakdown, BudgetFeasibility, Expense, Money, PriceStatus, Provenance
from app.evidence.service import normalize_money


class BudgetValidationError(ValueError):
    pass


_ZERO_DECIMAL_CURRENCIES = {"JPY", "KRW"}


def _round(amount: Decimal, currency: str) -> Decimal:
    quantum = Decimal("1") if currency in _ZERO_DECIMAL_CURRENCIES else Decimal("0.01")
    return amount.quantize(quantum, rounding=ROUND_HALF_UP)


def _converted(amount: Decimal, expense: Expense, currency: str) -> Decimal:
    if expense.money.currency == currency:
        return amount
    fx = expense.fx_snapshot
    if fx is None:
        raise BudgetValidationError(f"Expense {expense.id} needs an FX snapshot")
    if fx.base_currency == expense.money.currency and fx.quote_currency == currency:
        return amount * fx.rate
    if fx.quote_currency == expense.money.currency and fx.base_currency == currency:
        return amount / fx.rate
    raise BudgetValidationError(f"Expense {expense.id} FX snapshot does not match its currencies")


def _classify(money: Money) -> str:
    if money.status is PriceStatus.VERIFIED and money.provenance is Provenance.LIVE:
        return "verified"
    if money.status is PriceStatus.USER_PROVIDED:
        return "user"
    return "estimated"


def build_budget_breakdown(budget: Budget) -> BudgetBreakdown:
    if budget.target.amount is None:
        raise BudgetValidationError("Budget target must be known")
    currency = budget.target.currency
    subtotals = {"verified": Decimal(0), "estimated": Decimal(0), "user": Decimal(0)}
    taxes_total = Decimal(0)
    contingency_total = Decimal(0)
    unknown: list[str] = []
    mandatory_unknown: list[str] = []

    for expense in budget.expenses:
        if expense.included:
            continue
        normalized_money = normalize_money(expense.money, budget.evidence)
        if normalized_money.status is PriceStatus.UNKNOWN:
            unknown.append(expense.id)
            if expense.mandatory:
                mandatory_unknown.append(expense.id)
            continue
        assert normalized_money.amount is not None
        try:
            base = _converted(normalized_money.amount * expense.quantity, expense, currency)
            taxes = Decimal(0)
            if not expense.taxes_included:
                for tax in expense.taxes:
                    if tax.status is PriceStatus.UNKNOWN or tax.amount is None:
                        unknown.append(expense.id)
                        if expense.mandatory:
                            mandatory_unknown.append(expense.id)
                        continue
                    taxes += _converted(tax.amount, expense, currency)
        except BudgetValidationError:
            unknown.append(expense.id)
            if expense.mandatory:
                mandatory_unknown.append(expense.id)
            continue
        subtotals[_classify(normalized_money)] += base
        taxes_total += taxes
        if expense.category == "contingency":
            contingency_total += base

    verified = _round(subtotals["verified"], currency)
    estimated = _round(subtotals["estimated"], currency)
    user = _round(subtotals["user"], currency)
    taxes_total = _round(taxes_total, currency)
    contingency_total = _round(contingency_total, currency)
    known_total = _round(verified + estimated + user + taxes_total, currency)
    target = _round(budget.target.amount, currency)
    mandatory_unknown = list(dict.fromkeys(mandatory_unknown))
    unknown = list(dict.fromkeys(unknown))
    if mandatory_unknown:
        feasibility = BudgetFeasibility.UNKNOWN
        shortfall = None
    elif known_total > target:
        feasibility = BudgetFeasibility.OVER_BUDGET
        shortfall = _round(known_total - target, currency)
    else:
        feasibility = BudgetFeasibility.WITHIN_BUDGET
        shortfall = None
    return BudgetBreakdown(
        currency=currency,
        verified_subtotal=verified,
        estimated_subtotal=estimated,
        user_provided_subtotal=user,
        taxes_total=taxes_total,
        contingency_total=contingency_total,
        known_total=known_total,
        unknown_expense_ids=tuple(unknown),
        mandatory_unknown_expense_ids=tuple(mandatory_unknown),
        feasibility=feasibility,
        shortfall=shortfall,
    )
