from time import perf_counter

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.observability.metrics import emit_metrics


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        started = perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            emit_metrics("api_request", {"ApiRequestCount": 1, "ApiServerErrorCount": 1, "ApiLatencyMs": (perf_counter() - started) * 1000}, {"method": request.method, "status_class": "5xx"})
            raise
        status_class = f"{response.status_code // 100}xx"
        metrics = {"ApiRequestCount": 1, "ApiLatencyMs": (perf_counter() - started) * 1000}
        if response.status_code in {401, 403}:
            metrics["AuthorizationDenialCount"] = 1
        if response.status_code >= 500:
            metrics["ApiServerErrorCount"] = 1
        emit_metrics("api_request", metrics, {"method": request.method, "status_class": status_class})
        return response
