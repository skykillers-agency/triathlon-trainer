"""Unit tests for AI Triathlon Trainer endpoints and coach engine."""

from fastapi.testclient import TestClient
from app.main import app
from app.coach_engine import CoachEngine

client = TestClient(app)


def test_index_page():
    res = client.get("/")
    assert res.status_code == 200
    assert "AI Triathlon Trainer" in res.text


def test_status_endpoint():
    res = client.get("/api/status")
    assert res.status_code == 200
    data = res.json()
    assert "authenticated" in data


def test_readiness_endpoint():
    res = client.get("/api/readiness")
    assert res.status_code == 200
    data = res.json()
    assert "metrics" in data
    assert "coach_assessment" in data
    assert "score" in data["coach_assessment"]


def test_activities_endpoint():
    res = client.get("/api/activities")
    assert res.status_code == 200
    data = res.json()
    assert "activities" in data
    assert len(data["activities"]) > 0


def test_weekly_summary_endpoint():
    res = client.get("/api/weekly-summary")
    assert res.status_code == 200
    data = res.json()
    assert "disciplines" in data
    assert "swim" in data["disciplines"]
    assert "bike" in data["disciplines"]
    assert "run" in data["disciplines"]


def test_workout_generation_bike_sweetspot():
    payload = {
        "discipline": "bike",
        "workout_type": "sweetspot",
        "readiness_level": "PRIME",
        "target_duration_min": 75,
        "ftp_watts": 250,
    }
    res = client.post("/api/workouts/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert "workout" in data
    workout = data["workout"]
    assert workout["discipline"] == "bike"
    assert "Sweet Spot" in workout["name"]
    assert len(workout["steps"]) >= 5


def test_workout_generation_fatigue_adaptation():
    # If athlete is fatigued/recovering, it should throttle to recovery spin
    payload = {
        "discipline": "bike",
        "workout_type": "sweetspot",
        "readiness_level": "RECOVERY",
        "target_duration_min": 45,
        "ftp_watts": 250,
    }
    res = client.post("/api/workouts/generate", json=payload)
    assert res.status_code == 200
    data = res.json()
    workout = data["workout"]
    assert "Recovery" in workout["name"]


def test_workout_generation_brick():
    payload = {
        "discipline": "brick",
        "workout_type": "race_brick",
        "readiness_level": "PRIME",
        "target_duration_min": 75,
    }
    res = client.post("/api/workouts/generate", json=payload)
    assert res.status_code == 200
    workout = res.json()["workout"]
    assert workout["discipline"] == "brick"
    assert any("Transition" in s.get("type", "") for s in workout["steps"])


def test_coach_engine_scoring():
    # High readiness
    high = CoachEngine.calculate_readiness_score({
        "sleep_score": 92,
        "sleep_duration_hours": 8.2,
        "hrv_status": "BALANCED",
        "body_battery_current": 95,
        "stress_avg": 18,
    })
    assert high["level"] == "PRIME"
    assert high["score"] >= 75

    # Low readiness
    low = CoachEngine.calculate_readiness_score({
        "sleep_score": 45,
        "sleep_duration_hours": 4.5,
        "hrv_status": "LOW",
        "body_battery_current": 25,
        "stress_avg": 65,
    })
    assert low["level"] == "RECOVERY"
    assert low["score"] < 50
