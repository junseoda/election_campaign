from pathlib import Path
import os
import sys
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn


# Run example:
# uvicorn backend.main:app --reload
# uvicorn main:app --host 0.0.0.0 --port $PORT
# python backend/main.py
BACKEND_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = BACKEND_ROOT.parent
for import_root in (PROJECT_ROOT, BACKEND_ROOT):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from scripts.message_rules import recommend_messages  # noqa: E402
from scripts.recommender import recommend_places  # noqa: E402
try:
    from backend.district_utils import normalize_districts, validate_recommendation_districts  # noqa: E402
except ModuleNotFoundError:
    from district_utils import normalize_districts, validate_recommendation_districts  # type: ignore  # noqa: E402
from scripts.route_planner import build_campaign_route  # noqa: E402
try:
    from services.dashboard_service import (  # type: ignore  # noqa: E402
        get_candidate_coverage_dashboard,
        get_evaluation_dashboard,
        get_gold_queries,
        get_optimized_recommendations,
    )
    from services.route_service import (  # type: ignore  # noqa: E402
        get_route_options,
        get_sample_route,
        recommend_route,
    )
except ModuleNotFoundError:
    from backend.services.dashboard_service import (  # noqa: E402
        get_candidate_coverage_dashboard,
        get_evaluation_dashboard,
        get_gold_queries,
        get_optimized_recommendations,
    )
    from backend.services.route_service import (  # noqa: E402
        get_route_options,
        get_sample_route,
        recommend_route,
    )


TimeSlot = Literal["morning", "afternoon"]
PlaceType = Literal["subway", "park", "market", "senior_friendly"]
TargetAgeGroup = Literal["20_40", "60_plus"]
RouteTemplate = Literal["default", "neighborhood_focus"]


class RecommendRequest(BaseModel):
    time_slot: TimeSlot
    place_type: PlaceType
    target_age_group: TargetAgeGroup
    district: str | None = None
    districts: list[str] | str | None = None
    selectedDistricts: list[str] | str | None = None
    top_n: int = 3


class HealthResponse(BaseModel):
    status: str


class RouteRequest(BaseModel):
    target_age_group: TargetAgeGroup
    route_template: RouteTemplate = "default"
    district: str | None = None
    districts: list[str] | str | None = None
    selectedDistricts: list[str] | str | None = None


class PlaceRecommendation(BaseModel):
    place_id: str | None = None
    name: str
    place_type: str | None = None
    district_name: str | None = None
    district: str | None = None
    district_normalized: str | None = None
    district_match: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    score: float
    reason: list[str]


class MessageRecommendation(BaseModel):
    message: str
    reason: str


class RecommendResponse(BaseModel):
    input: RecommendRequest
    places: list[PlaceRecommendation]
    messages: list[MessageRecommendation]
    debug: dict[str, Any] | None = None


class RouteItem(BaseModel):
    time: str
    time_slot: TimeSlot
    place_type: PlaceType
    place: PlaceRecommendation | None
    messages: list[MessageRecommendation]


class RouteResponse(BaseModel):
    target_age_group: TargetAgeGroup
    route_template: RouteTemplate
    route: list[RouteItem]


app = FastAPI(title="Campaign Recommendation MVP API")


def _cors_origins() -> list[str]:
    defaults = [
        "https://election-campaign-coral.vercel.app",
        "https://election-campaign-junseodas-projects.vercel.app",
        "https://election-campaign-git-main-junseodas-projects.vercel.app",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ]
    configured = [
        origin.strip()
        for origin in os.getenv("BACKEND_CORS_ORIGINS", "").split(",")
        if origin.strip()
    ]
    return list(dict.fromkeys([*defaults, *configured]))


app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins(),
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def warm_backend_cache() -> None:
    get_sample_route()
    get_gold_queries(limit=1)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(_, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={
            "detail": "invalid request",
            "errors": exc.errors(),
        },
    )


@app.get("/health", response_model=HealthResponse)
def health() -> dict:
    return {"status": "ok"}


@app.post("/recommend", response_model=RecommendResponse)
def recommend(payload: RecommendRequest) -> dict:
    try:
        selected_districts = normalize_districts(
            [
                *([payload.district] if payload.district else []),
                *(payload.districts if isinstance(payload.districts, list) else [payload.districts] if payload.districts else []),
                *(
                    payload.selectedDistricts
                    if isinstance(payload.selectedDistricts, list)
                    else [payload.selectedDistricts]
                    if payload.selectedDistricts
                    else []
                ),
            ]
        )
        recommendation_payload = recommend_places(
            payload.time_slot,
            payload.place_type,
            payload.target_age_group,
            top_n=max(1, int(payload.top_n or 3)),
            selected_districts=selected_districts,
            include_debug=True,
        )
        places = recommendation_payload["places"]
        places, validation_warnings = validate_recommendation_districts(places, selected_districts)
        debug = {
            **recommendation_payload.get("debug", {}),
            "selected_districts": selected_districts,
            "district_mismatch_count": 0,
            "warnings": [
                *recommendation_payload.get("debug", {}).get("warnings", []),
                *validation_warnings,
            ],
        }
        messages = recommend_messages(
            payload.place_type,
            payload.target_age_group,
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "input": payload.model_dump(),
        "places": places,
        "messages": messages,
        "debug": debug,
    }


def _request_selected_districts(payload: Any) -> list[str]:
    return normalize_districts(
        [
            *([payload.district] if getattr(payload, "district", None) else []),
            *(
                payload.districts
                if isinstance(getattr(payload, "districts", None), list)
                else [payload.districts]
                if getattr(payload, "districts", None)
                else []
            ),
            *(
                payload.selectedDistricts
                if isinstance(getattr(payload, "selectedDistricts", None), list)
                else [payload.selectedDistricts]
                if getattr(payload, "selectedDistricts", None)
                else []
            ),
        ]
    )


@app.post("/route", response_model=RouteResponse)
def route(payload: RouteRequest) -> dict:
    try:
        campaign_route = build_campaign_route(
            payload.target_age_group,
            payload.route_template,
            selected_districts=_request_selected_districts(payload),
        )
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error

    return {
        "target_age_group": payload.target_age_group,
        "route_template": payload.route_template,
        "route": campaign_route,
    }


def _dashboard_error_response(error: Exception) -> HTTPException:
    if isinstance(error, FileNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=400, detail=str(error))
    return HTTPException(status_code=500, detail=str(error))


@app.get("/optimized/queries")
def optimized_queries(limit: int = 100) -> dict:
    try:
        return get_gold_queries(limit=limit)
    except Exception as error:
        raise _dashboard_error_response(error) from error


@app.get("/optimized/recommendations")
def optimized_recommendations(query_id: str | None = None, limit: int = 10) -> dict:
    try:
        return get_optimized_recommendations(query_id=query_id, limit=limit)
    except Exception as error:
        raise _dashboard_error_response(error) from error


@app.get("/evaluation/dashboard")
def evaluation_dashboard() -> dict:
    try:
        return get_evaluation_dashboard()
    except Exception as error:
        raise _dashboard_error_response(error) from error


@app.get("/coverage/dashboard")
def coverage_dashboard(limit: int = 15) -> dict:
    try:
        return get_candidate_coverage_dashboard(limit=limit)
    except Exception as error:
        raise _dashboard_error_response(error) from error


@app.get("/route/options")
def route_options() -> dict:
    try:
        return get_route_options()
    except Exception as error:
        raise _dashboard_error_response(error) from error


@app.post("/route/recommend")
def route_recommend(payload: dict) -> dict:
    try:
        return recommend_route(payload)
    except Exception as error:
        raise _dashboard_error_response(error) from error


@app.get("/route/sample")
def route_sample() -> dict:
    try:
        return get_sample_route()
    except Exception as error:
        raise _dashboard_error_response(error) from error


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="127.0.0.1", port=8000, reload=False)
