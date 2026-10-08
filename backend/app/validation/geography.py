from decimal import Decimal

from app.domain.contracts import ValidationResult
from app.planning.geography import geodesic_km
from app.providers.places import ResolvedPlace


def validate_radius(anchor: ResolvedPlace, places: tuple[ResolvedPlace, ...], radius_km: Decimal) -> tuple[ValidationResult, ...]:
    return tuple(
        ValidationResult(rule="radius", severity="error", message=f"{place.name} is outside the {radius_km} km radius", entity_ids=(place.id,))
        for place in places if geodesic_km(anchor, place) > radius_km
    )
