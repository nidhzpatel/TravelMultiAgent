"""Version-pinned trip PDF rendering from canonical typed state."""

from collections.abc import Iterable
from datetime import datetime

from fpdf import FPDF

from app.domain.contracts import BudgetBreakdown, Evidence, TripVersion
from app.providers.alternatives import NormalizedProviderItem, ProviderRun


def _safe(value: object) -> str:
    return str(value).encode("latin-1", errors="replace").decode("latin-1")


def _line(pdf: FPDF, text: str, *, height: int = 6) -> None:
    pdf.multi_cell(0, height, _safe(text), new_x="LMARGIN", new_y="NEXT")


def _heading(pdf: FPDF, text: str, size: int = 13) -> None:
    pdf.set_font("Helvetica", "B", size)
    _line(pdf, text, height=8)
    pdf.set_font("Helvetica", size=10)


def _evidence(items: Iterable[NormalizedProviderItem], trip: TripVersion) -> tuple[Evidence, ...]:
    values = list(trip.trip.budget.evidence)
    for item in items:
        values.extend(item.evidence)
    return tuple({item.id: item for item in values}.values())


def render_trip_pdf(
    trip: TripVersion,
    budget: BudgetBreakdown,
    provider_items: tuple[NormalizedProviderItem, ...] = (),
    provider_runs: tuple[ProviderRun, ...] = (),
) -> bytes:
    pdf = FPDF()
    pdf.set_compression(False)
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_title(_safe(f"{trip.trip.title} - accepted version {trip.version}"))
    pdf.set_font("Helvetica", "B", 17)
    _line(pdf, trip.trip.title, height=10)
    pdf.set_font("Helvetica", size=10)
    _line(pdf, f"Accepted trip version: {trip.version}")
    _line(pdf, f"Exported at: {datetime.now().astimezone().isoformat(timespec='seconds')}")
    _line(pdf, f"Readiness: {trip.trip.readiness.value} (planning state; not a booking)")

    _heading(pdf, "Trip overview")
    _line(pdf, f"From: {trip.trip.brief.origin or 'UNKNOWN'}")
    _line(pdf, f"Destination: {trip.trip.brief.destination_text}")
    _line(pdf, f"Dates: {trip.trip.brief.start_date or 'UNKNOWN'} to {trip.trip.brief.end_date or 'UNKNOWN'}")
    _line(pdf, f"Travelers: {trip.trip.brief.travelers}")

    _heading(pdf, "Accepted timeline")
    if not trip.trip.days:
        _line(pdf, "No accepted scheduled days are available.")
    for day in trip.trip.days:
        pdf.set_font("Helvetica", "B", 11)
        _line(pdf, f"{day.local_date} - {day.timezone}")
        pdf.set_font("Helvetica", size=10)
        if not day.scheduled_items:
            _line(pdf, "  No accepted items.")
        for item in day.scheduled_items:
            start = item.start_at.isoformat() if item.start_at else "UNKNOWN"
            end = item.end_at.isoformat() if item.end_at else "UNKNOWN"
            _line(pdf, f"  {item.kind.upper()} | {start} to {end} | entity {item.entity_id}")

    _heading(pdf, "Budget and uncertainty")
    _line(pdf, f"Known total: {budget.currency} {budget.known_total}")
    _line(pdf, f"Budget feasibility: {budget.feasibility.value}")
    _line(pdf, f"Unknown expenses: {', '.join(budget.unknown_expense_ids) or 'none'}")
    _line(pdf, f"Mandatory unknown expenses: {', '.join(budget.mandatory_unknown_expense_ids) or 'none'}")
    non_success = tuple(run for run in provider_runs if run.status.value != "SUCCESS")
    if non_success:
        for run in non_success:
            _line(pdf, f"Provider uncertainty: {run.kind.value}/{run.provider} = {run.status.value} ({run.error_code or 'no code'})")
    elif not provider_runs:
        _line(pdf, "Provider status: no version-pinned provider runs are available.")

    _heading(pdf, "Sources and provenance")
    evidence = _evidence(provider_items, trip)
    if not evidence:
        _line(pdf, "No retained source evidence is available for this accepted version.")
    for item in evidence:
        _line(pdf, f"{item.source} | {item.provenance.value}/{item.provider_outcome.value} | retrieved {item.retrieved_at.isoformat()}")
        _line(pdf, f"  Reference: {item.reference_url or 'not retained'}")
        _line(pdf, f"  Covers: {', '.join(item.covered_fields) or 'unspecified'}")

    _line(pdf, "Generated from immutable accepted state. Pending previews are excluded.")
    return bytes(pdf.output())
