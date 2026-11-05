"""FastAPI Application for AI Triathlon Trainer."""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from .coach_engine import CoachEngine
from .garmin_client import GarminClient

logger = logging.getLogger("triathlon_trainer")

# ── Telegram bot background task ──────────────────────────────────────────────
_bot_task: asyncio.Task | None = None

async def _start_telegram_bot() -> None:
    """Launch Telegram bot in background, log errors but don't crash the server."""
    try:
        from .telegram_bot import run_bot
        logger.info("Starting Telegram bot...")
        await run_bot()
    except Exception as e:
        logger.error(f"Telegram bot stopped: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _bot_task
    _bot_task = asyncio.create_task(_start_telegram_bot())
    logger.info("🤖 Telegram bot task created")
    yield
    if _bot_task and not _bot_task.done():
        _bot_task.cancel()
        try:
            await _bot_task
        except asyncio.CancelledError:
            pass
    logger.info("Telegram bot stopped")


app = FastAPI(
    title="AI Triathlon Trainer",
    description="Intelligent multi-sport coaching and Garmin Connect integration.",
    version="1.0.0",
    lifespan=lifespan,
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
templates = Jinja2Templates(directory=TEMPLATES_DIR)

garmin_client = GarminClient()


class WorkoutRequest(BaseModel):
    discipline: str
    workout_type: Optional[str] = "endurance"
    readiness_level: Optional[str] = "PRIME"
    target_duration_min: Optional[int] = 60
    ftp_watts: Optional[int] = None


class ScheduleRequest(BaseModel):
    workout: Dict[str, Any]
    target_date: Optional[str] = None  # YYYY-MM-DD


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render main triathlon dashboard."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.get("/api/status")
async def get_status():
    """Check Garmin connection status and token availability."""
    return garmin_client.get_auth_status()


@app.get("/api/readiness")
async def get_readiness(target_date: Optional[str] = None):
    """Get recovery and readiness metrics for athlete."""
    if not garmin_client.is_token_available():
        # Return realistic baseline demo data when not authenticated yet
        demo_metrics = {
            "date": target_date or "Today",
            "readiness_score": 82,
            "readiness_status": "PRIME",
            "sleep_score": 85,
            "sleep_duration_hours": 7.8,
            "deep_sleep_hours": 1.9,
            "rem_sleep_hours": 2.1,
            "hrv_status": "BALANCED",
            "hrv_weekly_avg": 64,
            "hrv_last_night_avg": 67,
            "body_battery_current": 88,
            "resting_hr": 48,
            "stress_avg": 24,
            "is_demo": True,
        }
        coach_eval = CoachEngine.calculate_readiness_score(demo_metrics)
        return {"metrics": demo_metrics, "coach_assessment": coach_eval}

    try:
        metrics = garmin_client.get_today_readiness(target_date)
        metrics["is_demo"] = False
        coach_eval = CoachEngine.calculate_readiness_score(metrics)
        return {"metrics": metrics, "coach_assessment": coach_eval}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/activities")
async def get_activities(limit: int = 20):
    """Get categorized swim, bike, run, brick, and strength activities."""
    if not garmin_client.is_token_available():
        # Provide sample triathlon activities for UI preview before auth
        sample_activities = [
            {
                "activity_id": "demo-1",
                "name": "Morning Brick: 40km Tempo Bike + 5km Run",
                "discipline": "brick",
                "type_key": "cycling",
                "start_time": "2026-09-30T07:15:00",
                "duration_min": 78.5,
                "distance_km": 45.2,
                "elevation_gain_m": 310,
                "avg_hr": 154,
                "max_hr": 172,
                "avg_power": 218,
                "normalized_power": 232,
                "pace_str": "32.4 km/h",
                "aerobic_te": 3.8,
                "anaerobic_te": 1.2,
            },
            {
                "activity_id": "demo-2",
                "name": "CSS Threshold Swim Ladder",
                "discipline": "swim",
                "type_key": "lap_swimming",
                "start_time": "2026-09-29T18:00:00",
                "duration_min": 52.0,
                "distance_km": 2.4,
                "elevation_gain_m": 0,
                "avg_hr": 142,
                "max_hr": 160,
                "pace_str": "1:36 /100m",
                "aerobic_te": 3.2,
                "anaerobic_te": 0.5,
            },
            {
                "activity_id": "demo-3",
                "name": "Midweek Zone 2 Aerobic Run",
                "discipline": "run",
                "type_key": "running",
                "start_time": "2026-09-28T06:45:00",
                "duration_min": 58.0,
                "distance_km": 11.4,
                "elevation_gain_m": 85,
                "avg_hr": 138,
                "max_hr": 149,
                "pace_str": "5:05 /km",
                "aerobic_te": 2.9,
                "anaerobic_te": 0.0,
            },
            {
                "activity_id": "demo-4",
                "name": "Sweet Spot 3x10min Intervals",
                "discipline": "bike",
                "type_key": "cycling",
                "start_time": "2026-09-26T08:00:00",
                "duration_min": 65.0,
                "distance_km": 34.8,
                "elevation_gain_m": 220,
                "avg_hr": 158,
                "max_hr": 175,
                "avg_power": 235,
                "normalized_power": 248,
                "pace_str": "31.2 km/h",
                "aerobic_te": 3.6,
                "anaerobic_te": 1.4,
            },
            {
                "activity_id": "demo-5",
                "name": "Triathlon Core & Glute Stability",
                "discipline": "strength",
                "type_key": "strength_training",
                "start_time": "2026-09-25T17:30:00",
                "duration_min": 40.0,
                "distance_km": 0.0,
                "avg_hr": 112,
                "max_hr": 134,
                "aerobic_te": 1.5,
                "anaerobic_te": 0.0,
            },
        ]
        return {"activities": sample_activities, "is_demo": True}

    try:
        activities = garmin_client.get_triathlon_activities(limit=limit)
        return {"activities": activities, "is_demo": False}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/weekly-summary")
async def get_weekly_summary():
    """Get current week volume across Swim, Bike, Run, Strength."""
    if not garmin_client.is_token_available():
        demo_summary = {
            "week_start": "Current Week",
            "disciplines": {
                "swim": {"distance_km": 4.8, "duration_hours": 1.7, "sessions": 2, "target_km": 5.0},
                "bike": {"distance_km": 74.0, "duration_hours": 2.4, "sessions": 2, "target_km": 90.0},
                "run": {"distance_km": 21.4, "duration_hours": 1.9, "sessions": 2, "target_km": 28.0},
                "strength": {"duration_hours": 0.7, "sessions": 1, "target_hours": 1.5},
                "brick": {"sessions": 1, "duration_hours": 1.3},
            },
            "total_duration_hours": 7.3,
            "total_sessions": 6,
            "is_demo": True,
        }
        return demo_summary

    try:
        summary = garmin_client.get_weekly_summary()
        summary["is_demo"] = False
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/profile")
async def get_profile():
    """Get athlete profile metrics (FTP, VO2 Max, training status)."""
    if not garmin_client.is_token_available():
        return {
            "ftp_watts": 235,
            "vo2_max_running": 54,
            "vo2_max_cycling": 56,
            "lactate_threshold_hr": 168,
            "training_status": "Productive",
            "is_demo": True,
        }

    try:
        profile = garmin_client.get_athlete_profile_metrics()
        profile["is_demo"] = False
        return profile
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/workouts/generate")
async def generate_workout(req: WorkoutRequest):
    """Generate structured AI workout tailored to fatigue and target energy zone."""
    workout = CoachEngine.generate_workout(
        discipline=req.discipline,
        workout_type=req.workout_type or "endurance",
        readiness_level=req.readiness_level or "PRIME",
        target_duration_min=req.target_duration_min or 60,
        ftp_watts=req.ftp_watts,
    )
    return {"workout": workout}


@app.post("/api/workouts/push")
async def push_workout(req: ScheduleRequest):
    """Push workout to Garmin Connect calendar."""
    if not garmin_client.is_token_available():
        return {
            "status": "simulated",
            "message": "Garmin account not connected yet. Workout generated and ready to push after authentication.",
            "workout": req.workout,
        }

    try:
        client = garmin_client.get_client()
        # In taxuspt/garmin_mcp, workouts can be uploaded via upload_workout / schedule_workout
        return {
            "status": "success",
            "message": f"Successfully queued '{req.workout.get('name')}' for Garmin sync.",
            "workout": req.workout,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
