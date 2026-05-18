from pathlib import Path
import sys
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn


# Run example:
# uvicorn backend.main:app --reload
# python backend/main.py
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.message_rules import recommend_messages  # noqa: E402
from scripts.recommender import recommend_places  # noqa: E402
from scripts.route_planner import build_campaign_route  # noqa: E402
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


class HealthResponse(BaseModel):
    status: str


class RouteRequest(BaseModel):
    target_age_group: TargetAgeGroup
    route_template: RouteTemplate = "default"


class PlaceRecommendation(BaseModel):
    name: str
    score: float
    reason: list[str]


class MessageRecommendation(BaseModel):
    message: str
    reason: str


class RecommendResponse(BaseModel):
    input: RecommendRequest
    places: list[PlaceRecommendation]
    messages: list[MessageRecommendation]


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
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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
        places = recommend_places(
            payload.time_slot,
            payload.place_type,
            payload.target_age_group,
        )
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
    }


@app.post("/route", response_model=RouteResponse)
def route(payload: RouteRequest) -> dict:
    try:
        campaign_route = build_campaign_route(
            payload.target_age_group,
            payload.route_template,
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
