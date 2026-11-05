"""Garmin Connect Client for AI Triathlon Trainer.

Loads cached OAuth tokens from ~/.garminconnect (generated via garmin-mcp-auth)
and exposes triathlon-specific metrics, recovery data, and workout management.
"""

from __future__ import annotations

import os
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger("garmin_client")

TOKEN_DIR = os.path.expanduser(os.environ.get("GARMIN_TOKEN_PATH", "~/.garminconnect"))


class GarminClient:
    def __init__(self, token_dir: str = TOKEN_DIR):
        self.token_dir = os.path.expanduser(token_dir)
        self._client = None
        self._cached_profile = None
        self._ensure_tokens_from_env()

    def _ensure_tokens_from_env(self) -> None:
        """If token files do not exist, auto-restore from GARMIN_TOKENS_BASE64 or GARMIN_TOKENS_JSON env vars."""
        target_file = os.path.join(self.token_dir, "garmin_tokens.json")
        if os.path.exists(target_file):
            return

        b64 = os.environ.get("GARMIN_TOKENS_BASE64")
        raw_json = os.environ.get("GARMIN_TOKENS_JSON")

        if b64 or raw_json:
            try:
                import base64
                os.makedirs(self.token_dir, exist_ok=True)
                content = base64.b64decode(b64.strip()).decode("utf-8") if b64 else raw_json
                with open(target_file, "w") as f:
                    f.write(content)
                logger.info("Restored Garmin tokens from environment variable")
            except Exception as e:
                logger.warning(f"Failed to restore tokens from env: {e}")

    def is_token_available(self) -> bool:
        """Check if OAuth token directory exists and contains token files."""
        self._ensure_tokens_from_env()
        if not os.path.exists(self.token_dir):
            return False
        # GarminConnect typically writes oauth1_token.json and oauth2_token.json
        files = os.listdir(self.token_dir)
        return any("token" in f.lower() or "oauth" in f.lower() for f in files)

    def get_client(self):
        """Get or initialize authenticated GarminConnect client.

        Uses garminconnect's load() method to read DI OAuth tokens stored by
        garmin-mcp-auth in ~/.garminconnect/garmin_tokens.json.
        """
        if self._client is not None:
            return self._client

        if not self.is_token_available():
            raise RuntimeError(
                f"Garmin tokens not found in '{self.token_dir}'. "
                "Please authenticate using 'uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp-auth' first."
            )

        try:
            from garminconnect import Garmin

            client = Garmin()
            # login(tokenstore=path) reads garmin_tokens.json (DI OAuth format)
            client.login(tokenstore=self.token_dir)
            self._client = client
            return self._client
        except Exception as e:
            logger.error(f"Failed to load Garmin tokens: {e}")
            raise

    def get_auth_status(self) -> Dict[str, Any]:
        """Return authentication status and user details if available."""
        token_exists = self.is_token_available()
        if not token_exists:
            return {
                "authenticated": False,
                "token_dir": self.token_dir,
                "message": "Garmin tokens not found. Run garmin-mcp-auth to connect your account.",
            }

        try:
            client = self.get_client()
            if not self._cached_profile:
                name = client.get_full_name()
                self._cached_profile = {"name": name}
            return {
                "authenticated": True,
                "token_dir": self.token_dir,
                "user": self._cached_profile.get("name", "Athlete"),
                "message": "Connected to Garmin Connect",
            }
        except Exception as e:
            return {
                "authenticated": False,
                "token_dir": self.token_dir,
                "error": str(e),
                "message": "Authentication failed with saved tokens. Re-authentication may be required.",
            }

    def get_today_readiness(self, target_date: Optional[str] = None) -> Dict[str, Any]:
        """Fetch recovery & physiological readiness metrics for a date (YYYY-MM-DD)."""
        target = target_date or date.today().isoformat()
        client = self.get_client()

        readiness: Dict[str, Any] = {
            "date": target,
            "readiness_score": None,
            "readiness_status": "UNKNOWN",
            "sleep_score": None,
            "sleep_duration_hours": None,
            "deep_sleep_hours": None,
            "rem_sleep_hours": None,
            "hrv_status": "UNKNOWN",
            "hrv_weekly_avg": None,
            "hrv_last_night_avg": None,
            "body_battery_current": None,
            "body_battery_charged": None,
            "body_battery_drained": None,
            "resting_hr": None,
            "stress_avg": None,
        }

        # 1. Training Readiness (newer Garmin devices)
        try:
            tr_data = client.get_training_readiness(target)
            if tr_data:
                # May be list or dict depending on endpoint response
                first = tr_data[0] if isinstance(tr_data, list) and tr_data else tr_data
                if isinstance(first, dict):
                    readiness["readiness_score"] = first.get("score")
                    readiness["readiness_status"] = first.get("level", "MODERATE")
        except Exception as e:
            logger.debug(f"Training readiness not available: {e}")

        # 2. Sleep Data
        try:
            sleep = client.get_sleep_data(target)
            if sleep and isinstance(sleep, dict):
                daily = sleep.get("dailySleepDTO", {})
                readiness["sleep_score"] = daily.get("sleepScores", {}).get("overall", {}).get("value")
                sec = daily.get("sleepTimeSeconds", 0)
                readiness["sleep_duration_hours"] = round(sec / 3600, 1) if sec else None
                deep = daily.get("deepSleepSeconds", 0)
                readiness["deep_sleep_hours"] = round(deep / 3600, 1) if deep else None
                rem = daily.get("remSleepSeconds", 0)
                readiness["rem_sleep_hours"] = round(rem / 3600, 1) if rem else None
        except Exception as e:
            logger.debug(f"Sleep data error: {e}")

        # 3. HRV Data
        try:
            hrv = client.get_hrv_data(target)
            if hrv and isinstance(hrv, dict):
                summary = hrv.get("hrvSummary", {})
                readiness["hrv_status"] = summary.get("status", "UNKNOWN")
                readiness["hrv_weekly_avg"] = summary.get("weeklyAvg")
                readiness["hrv_last_night_avg"] = summary.get("lastNightAvg")
        except Exception as e:
            logger.debug(f"HRV data error: {e}")

        # 4. Body Battery
        try:
            bb = client.get_body_battery(target, target)
            if bb and isinstance(bb, list) and len(bb) > 0:
                first = bb[0]
                readiness["body_battery_charged"] = first.get("charged")
                readiness["body_battery_drained"] = first.get("drained")
                readiness["body_battery_current"] = first.get("bodyBatteryValuesArray", [{}])[-1].get("value") if first.get("bodyBatteryValuesArray") else None
        except Exception as e:
            logger.debug(f"Body battery error: {e}")

        # 5. Resting Heart Rate
        try:
            rhr = client.get_rhr_day(target)
            if rhr and isinstance(rhr, dict):
                readiness["resting_hr"] = rhr.get("restingHeartRate")
        except Exception as e:
            logger.debug(f"RHR error: {e}")

        # 6. Stress Data
        try:
            stress = client.get_stress_data(target)
            if stress and isinstance(stress, dict):
                readiness["stress_avg"] = stress.get("avgStressLevel")
        except Exception as e:
            logger.debug(f"Stress error: {e}")

        return readiness

    def get_triathlon_activities(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Fetch and categorize recent activities into Swim, Bike, Run, Strength, and Brick."""
        client = self.get_client()
        raw_activities = client.get_activities(0, limit)
        processed: List[Dict[str, Any]] = []

        for act in raw_activities:
            type_key = act.get("activityType", {}).get("typeKey", "").lower()
            name = act.get("activityName", "Activity")
            start_time = act.get("startTimeLocal", "")
            duration_sec = act.get("duration", 0) or 0
            distance_m = act.get("distance", 0) or 0
            elevation_m = act.get("elevationGain", 0) or 0
            avg_hr = act.get("averageHR")
            max_hr = act.get("maxHR")
            avg_speed_mps = act.get("averageSpeed", 0) or 0  # meters per second
            avg_power = act.get("avgPower")
            norm_power = act.get("normPower")
            aerobic_te = act.get("aerobicTrainingEffect")
            anaerobic_te = act.get("anaerobicTrainingEffect")

            # Determine triathlon discipline
            discipline = "other"
            if any(k in type_key for k in ["swim", "lap_swimming", "open_water"]):
                discipline = "swim"
            elif any(k in type_key for k in ["cycling", "biking", "virtual_ride", "gravel"]):
                discipline = "bike"
            elif any(k in type_key for k in ["run", "trail_running", "treadmill"]):
                discipline = "run"
            elif any(k in type_key for k in ["strength", "fitness_equipment", "weight"]):
                discipline = "strength"
            elif "transition" in type_key or "multisport" in type_key:
                discipline = "brick"

            # Formatted pace / speed
            pace_str = ""
            if discipline == "run" and avg_speed_mps > 0:
                sec_per_km = 1000.0 / avg_speed_mps
                mins = int(sec_per_km // 60)
                secs = int(sec_per_km % 60)
                pace_str = f"{mins}:{secs:02d} /km"
            elif discipline == "swim" and avg_speed_mps > 0:
                sec_per_100m = 100.0 / avg_speed_mps
                mins = int(sec_per_100m // 60)
                secs = int(sec_per_100m % 60)
                pace_str = f"{mins}:{secs:02d} /100m"
            elif discipline == "bike" and avg_speed_mps > 0:
                kmh = round(avg_speed_mps * 3.6, 1)
                pace_str = f"{kmh} km/h"

            processed.append({
                "activity_id": act.get("activityId"),
                "name": name,
                "discipline": discipline,
                "type_key": type_key,
                "start_time": start_time,
                "duration_min": round(duration_sec / 60, 1),
                "distance_km": round(distance_m / 1000.0, 2),
                "distance_m": round(distance_m),
                "elevation_gain_m": round(elevation_m),
                "avg_hr": round(avg_hr) if avg_hr else None,
                "max_hr": round(max_hr) if max_hr else None,
                "avg_power": round(avg_power) if avg_power else None,
                "normalized_power": round(norm_power) if norm_power else None,
                "pace_str": pace_str,
                "aerobic_te": aerobic_te,
                "anaerobic_te": anaerobic_te,
            })

        return processed

    def get_weekly_summary(self) -> Dict[str, Any]:
        """Aggregate current week volume across Swim, Bike, Run, Strength."""
        activities = self.get_triathlon_activities(limit=50)
        today = datetime.now()
        start_of_week = today - timedelta(days=today.weekday())
        start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)

        summary = {
            "week_start": start_of_week.strftime("%Y-%m-%d"),
            "disciplines": {
                "swim": {"distance_km": 0.0, "duration_hours": 0.0, "sessions": 0, "target_km": 4.0},
                "bike": {"distance_km": 0.0, "duration_hours": 0.0, "sessions": 0, "target_km": 80.0},
                "run": {"distance_km": 0.0, "duration_hours": 0.0, "sessions": 0, "target_km": 25.0},
                "strength": {"duration_hours": 0.0, "sessions": 0, "target_hours": 1.5},
                "brick": {"sessions": 0, "duration_hours": 0.0},
            },
            "total_duration_hours": 0.0,
            "total_sessions": 0,
        }

        for act in activities:
            try:
                act_time = datetime.fromisoformat(act["start_time"].replace("Z", "+00:00")).replace(tzinfo=None)
            except Exception:
                continue

            if act_time >= start_of_week:
                disc = act["discipline"]
                hours = round(act["duration_min"] / 60.0, 2)
                summary["total_duration_hours"] += hours
                summary["total_sessions"] += 1

                if disc in summary["disciplines"]:
                    summary["disciplines"][disc]["sessions"] += 1
                    summary["disciplines"][disc]["duration_hours"] += hours
                    if "distance_km" in summary["disciplines"][disc]:
                        summary["disciplines"][disc]["distance_km"] += act["distance_km"]

        # Round values cleanly
        summary["total_duration_hours"] = round(summary["total_duration_hours"], 1)
        for disc, data in summary["disciplines"].items():
            if "distance_km" in data:
                data["distance_km"] = round(data["distance_km"], 2)
            data["duration_hours"] = round(data["duration_hours"], 1)

        return summary

    def get_athlete_profile_metrics(self) -> Dict[str, Any]:
        """Fetch FTP, VO2 Max, Lactate Threshold, and Training Status."""
        client = self.get_client()
        metrics = {
            "ftp_watts": None,
            "vo2_max_running": None,
            "vo2_max_cycling": None,
            "lactate_threshold_hr": None,
            "training_status": "Productive",
        }

        try:
            ftp = client.get_cycling_ftp()
            if ftp and isinstance(ftp, dict):
                metrics["ftp_watts"] = ftp.get("ftp")
        except Exception:
            pass

        try:
            status = client.get_training_status()
            if status and isinstance(status, dict):
                metrics["training_status"] = status.get("trainingStatus", "Productive")
        except Exception:
            pass

        return metrics

    def get_scheduled_workouts(self, days_ahead: int = 14) -> List[Dict[str, Any]]:
        """Fetch scheduled workouts from Garmin calendar from today onwards."""
        client = self.get_client()
        today = date.today()
        months_to_check = {(today.year, today.month)}
        end_date = today + timedelta(days=days_ahead)
        months_to_check.add((end_date.year, end_date.month))

        scheduled_items: List[Dict[str, Any]] = []
        for y, m in sorted(months_to_check):
            try:
                res = client.get_scheduled_workouts(y, m)
                items = res.get("calendarItems", []) if isinstance(res, dict) else []
                for item in items:
                    item_date_str = item.get("date")
                    if not item_date_str:
                        continue
                    try:
                        item_date = date.fromisoformat(item_date_str[:10])
                    except Exception:
                        continue

                    if today <= item_date <= end_date:
                        sport = item.get("sportTypeKey", "other")
                        disc = "other"
                        if any(k in sport.lower() for k in ["cycling", "biking", "virtual_ride"]):
                            disc = "bike"
                        elif any(k in sport.lower() for k in ["run", "treadmill"]):
                            disc = "run"
                        elif "swim" in sport.lower():
                            disc = "swim"
                        elif "strength" in sport.lower():
                            disc = "strength"

                        scheduled_items.append({
                            "schedule_id": item.get("id"),
                            "workout_id": item.get("workoutId"),
                            "title": item.get("title") or "Scheduled Workout",
                            "date": item_date_str,
                            "discipline": disc,
                            "sport_type": sport,
                        })
            except Exception as e:
                logger.debug(f"Error fetching scheduled workouts for {y}-{m}: {e}")

        scheduled_items.sort(key=lambda x: x["date"])
        return scheduled_items
