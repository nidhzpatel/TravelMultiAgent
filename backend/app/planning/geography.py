"""Deterministic geodesic calculations; never route-duration estimates."""

from decimal import Decimal
from math import asin, cos, radians, sin, sqrt

from app.providers.places import ResolvedPlace


def geodesic_km(origin: ResolvedPlace, destination: ResolvedPlace) -> Decimal:
    lat1, lon1, lat2, lon2 = map(float, (origin.latitude, origin.longitude, destination.latitude, destination.longitude))
    dlat, dlon = radians(lat2 - lat1), radians(lon2 - lon1)
    value = sin(dlat / 2) ** 2 + cos(radians(lat1)) * cos(radians(lat2)) * sin(dlon / 2) ** 2
    return Decimal(str(6371.0088 * 2 * asin(sqrt(value))))
