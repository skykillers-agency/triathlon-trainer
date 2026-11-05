"""AI Triathlon Coaching Engine.

Provides readiness analysis, training stress calculations, and adaptive
workout generation for Swim, Bike, Run, Brick, and Strength sessions.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional


class CoachEngine:
    """Triathlon coaching intelligence engine."""

    @staticmethod
    def calculate_readiness_score(metrics: Dict[str, Any]) -> Dict[str, Any]:
        """Calculate composite recovery/readiness score (0-100) and actionable advice."""
        # If Garmin already provided an integrated readiness score, use it as baseline
        garmin_readiness = metrics.get("readiness_score")
        sleep_score = metrics.get("sleep_score")
        sleep_hours = metrics.get("sleep_duration_hours")
        hrv_status = (metrics.get("hrv_status") or "").upper()
        body_battery = metrics.get("body_battery_current") or metrics.get("body_battery_charged")
        stress = metrics.get("stress_avg")

        # Fallback / composite calculation if Garmin score not present
        if garmin_readiness is not None and garmin_readiness > 0:
            score = int(garmin_readiness)
        else:
            components = []
            weights = []

            if sleep_score is not None:
                components.append(sleep_score)
                weights.append(0.35)
            elif sleep_hours is not None:
                # 8 hours = 100%, 5 hours = 50%
                est_sleep = min(100.0, max(20.0, (sleep_hours / 8.0) * 100.0))
                components.append(est_sleep)
                weights.append(0.35)

            if body_battery is not None:
                components.append(body_battery)
                weights.append(0.25)

            # HRV contribution
            if "BALANCED" in hrv_status or "OPTIMAL" in hrv_status:
                components.append(90)
                weights.append(0.30)
            elif "UNBALANCED" in hrv_status:
                components.append(45)
                weights.append(0.30)
            elif "LOW" in hrv_status:
                components.append(25)
                weights.append(0.30)

            # Stress reduction
            if stress is not None:
                stress_factor = max(0, 100 - stress)
                components.append(stress_factor)
                weights.append(0.10)

            if components:
                total_weight = sum(weights)
                score = int(sum(c * w for c, w in zip(components, weights)) / total_weight)
            else:
                score = 75  # Default moderate baseline

        # Determine level & training guidance
        if score >= 75:
            level = "PRIME"
            badge_color = "emerald"
            headline = "Prime Condition — Green Light for High Intensity"
            advice = (
                "Your autonomic nervous system and sleep recovery are optimal. "
                "Today is an excellent day for key threshold, VO2 max intervals, or a demanding Brick session."
            )
            allowed_intensities = ["Z1", "Z2", "Z3", "SweetSpot", "Threshold", "VO2Max"]
        elif score >= 50:
            level = "MODERATE"
            badge_color = "amber"
            headline = "Moderate Readiness — Aerobic Endurance & Technique"
            advice = (
                "Your body is managing accumulated training load. "
                "Stick to Zone 2 aerobic base miles, CSS stroke drills, or steady cadence work. Avoid max-effort anaerobic reps."
            )
            allowed_intensities = ["Z1", "Z2", "Technique"]
        else:
            level = "RECOVERY"
            badge_color = "rose"
            headline = "High Physiological Strain — Active Recovery or Rest"
            advice = (
                "Elevated fatigue detected (suppressed HRV or deficient sleep). "
                "Prioritize recovery today: 30-min easy recovery spin, mobility/foam rolling, or a full rest day to prevent overtraining."
            )
            allowed_intensities = ["Z1", "Recovery", "Mobility"]

        return {
            "score": score,
            "level": level,
            "badge_color": badge_color,
            "headline": headline,
            "advice": advice,
            "allowed_intensities": allowed_intensities,
        }

    @staticmethod
    def generate_workout(
        discipline: str,
        workout_type: str,
        readiness_level: str = "PRIME",
        target_duration_min: int = 60,
        ftp_watts: Optional[int] = None,
    ) -> Dict[str, Any]:
        """Generate structured triathlon workout with target power, pace, or heart rate."""
        disc = discipline.lower()
        ftp = ftp_watts or 220  # Default baseline FTP if not configured

        # If athlete is fatigued, dynamically throttle high intensity
        is_recovery_day = readiness_level == "RECOVERY"

        if disc == "swim":
            if is_recovery_day or workout_type == "technique":
                return {
                    "name": "Swim: Technique & Aerobic Flush (1500m)",
                    "discipline": "swim",
                    "estimated_duration_min": 40,
                    "target_intensity": "Zone 1 / Zone 2",
                    "description": "Smooth recovery swim focusing on high elbow catch, rotation, and breathing symmetry.",
                    "steps": [
                        {"type": "Warmup", "distance_m": 300, "description": "Easy freestyle, focus on long glides."},
                        {"type": "Drill Set", "distance_m": 400, "description": "8x50m drill/swim alternating (catch-up, single-arm, fingertip drag) with 15s rest."},
                        {"type": "Pull Set", "distance_m": 400, "description": "4x100m pull buoy + paddles, smooth steady rhythm (CSS + 5s) with 20s rest."},
                        {"type": "Kick Set", "distance_m": 200, "description": "4x50m kickboard with fins, relaxed aerobic flutter kick."},
                        {"type": "Cooldown", "distance_m": 200, "description": "Super easy backstroke and breaststroke."},
                    ],
                }
            else:
                return {
                    "name": "Swim: CSS Threshold Ladder (2500m)",
                    "discipline": "swim",
                    "estimated_duration_min": 60,
                    "target_intensity": "Threshold (CSS Pace)",
                    "description": "Critical Swim Speed threshold intervals to build race-pace stamina without blowing up.",
                    "steps": [
                        {"type": "Warmup", "distance_m": 400, "description": "200m easy swim + 4x50m building pace 1-4."},
                        {"type": "Prep Set", "distance_m": 300, "description": "6x50m @ CSS pace with 15s rest."},
                        {"type": "Main Set 1", "distance_m": 800, "description": "2x400m holding steady CSS pace with 30s rest."},
                        {"type": "Main Set 2", "distance_m": 600, "description": "3x200m @ CSS minus 1-2s with 25s rest."},
                        {"type": "Speed Flush", "distance_m": 200, "description": "4x50m fast / easy by 25m with 20s rest."},
                        {"type": "Cooldown", "distance_m": 200, "description": "Relaxed recovery swim."},
                    ],
                }

        elif disc == "bike":
            if is_recovery_day:
                return {
                    "name": "Bike: Active Recovery Spin (45m)",
                    "discipline": "bike",
                    "estimated_duration_min": 45,
                    "target_intensity": "Zone 1 (< 55% FTP)",
                    "description": "Very light cadence flush. Keep pedaling easy at 90-95 rpm to clear metabolic waste.",
                    "steps": [
                        {"type": "Warmup", "duration_min": 10, "target": f"< {int(ftp * 0.50)}W (Z1)", "cadence": "88-92 rpm"},
                        {"type": "Steady Spin", "duration_min": 25, "target": f"{int(ftp * 0.50)}-{int(ftp * 0.55)}W (Z1)", "cadence": "90-95 rpm"},
                        {"type": "Cooldown", "duration_min": 10, "target": f"< {int(ftp * 0.45)}W", "cadence": "85 rpm"},
                    ],
                }
            elif workout_type == "sweetspot":
                ss_low = int(ftp * 0.88)
                ss_high = int(ftp * 0.93)
                return {
                    "name": "Bike: Sweet Spot 3x12m Intervals (75m)",
                    "discipline": "bike",
                    "estimated_duration_min": 75,
                    "target_intensity": f"Sweet Spot ({ss_low}-{ss_high}W, 88-93% FTP)",
                    "description": "High training stimulus with manageable fatigue. Ideal for half/full Ironman power foundation.",
                    "steps": [
                        {"type": "Warmup", "duration_min": 15, "target": f"110W building to {int(ftp * 0.75)}W", "cadence": "90 rpm"},
                        {"type": "Interval 1", "duration_min": 12, "target": f"{ss_low}-{ss_high}W", "cadence": "88-92 rpm"},
                        {"type": "Rest 1", "duration_min": 4, "target": f"< {int(ftp * 0.55)}W (Z1)", "cadence": "85 rpm"},
                        {"type": "Interval 2", "duration_min": 12, "target": f"{ss_low}-{ss_high}W", "cadence": "88-92 rpm"},
                        {"type": "Rest 2", "duration_min": 4, "target": f"< {int(ftp * 0.55)}W (Z1)", "cadence": "85 rpm"},
                        {"type": "Interval 3", "duration_min": 12, "target": f"{ss_low}-{ss_high}W", "cadence": "88-92 rpm"},
                        {"type": "Cooldown", "duration_min": 16, "target": f"< {int(ftp * 0.55)}W", "cadence": "85 rpm"},
                    ],
                }
            else:
                return {
                    "name": "Bike: Zone 2 Aerobic Base (90m)",
                    "discipline": "bike",
                    "estimated_duration_min": 90,
                    "target_intensity": f"Zone 2 ({int(ftp * 0.60)}-{int(ftp * 0.75)}W)",
                    "description": "Steady endurance miles to train fat oxidation and aerobic mitochondrial density.",
                    "steps": [
                        {"type": "Warmup", "duration_min": 15, "target": f"{int(ftp * 0.50)}-{int(ftp * 0.60)}W", "cadence": "88 rpm"},
                        {"type": "Endurance Block", "duration_min": 60, "target": f"{int(ftp * 0.65)}-{int(ftp * 0.73)}W", "cadence": "88-92 rpm"},
                        {"type": "Cooldown", "duration_min": 15, "target": f"< {int(ftp * 0.50)}W", "cadence": "85 rpm"},
                    ],
                }

        elif disc == "run":
            if is_recovery_day:
                return {
                    "name": "Run: Zone 2 Easy Shakeout (30m)",
                    "discipline": "run",
                    "estimated_duration_min": 30,
                    "target_intensity": "Zone 1 / Low Zone 2",
                    "description": "Gentle recovery jog. Strictly conversational effort, nasal breathing if possible.",
                    "steps": [
                        {"type": "Warmup Walk", "duration_min": 5, "target": "Brisk Walk / Dynamic Mobility"},
                        {"type": "Easy Jog", "duration_min": 20, "target": "Zone 1-2 HR (< 72% Max HR)"},
                        {"type": "Cooldown Walk", "duration_min": 5, "target": "Gentle Walk & Calf Stretch"},
                    ],
                }
            elif workout_type == "intervals":
                return {
                    "name": "Run: 5x1km Threshold Repeats (55m)",
                    "discipline": "run",
                    "estimated_duration_min": 55,
                    "target_intensity": "Zone 4 Lactate Threshold (10k Race Pace)",
                    "description": "Crucial running stamina builder for Olympic and 70.3 triathlon legs.",
                    "steps": [
                        {"type": "Warmup", "duration_min": 15, "target": "Z2 Easy Run + 4x15s dynamic strides"},
                        {"type": "Repeat 1", "distance_m": 1000, "target": "Threshold Pace / Z4 HR", "recovery": "90s jog"},
                        {"type": "Repeat 2", "distance_m": 1000, "target": "Threshold Pace / Z4 HR", "recovery": "90s jog"},
                        {"type": "Repeat 3", "distance_m": 1000, "target": "Threshold Pace / Z4 HR", "recovery": "90s jog"},
                        {"type": "Repeat 4", "distance_m": 1000, "target": "Threshold Pace / Z4 HR", "recovery": "90s jog"},
                        {"type": "Repeat 5", "distance_m": 1000, "target": "Threshold Pace / Z4 HR", "recovery": "90s jog"},
                        {"type": "Cooldown", "duration_min": 10, "target": "Very easy Z1 jog"},
                    ],
                }
            else:
                return {
                    "name": "Run: Progressive Aerobic Long Run (60m)",
                    "discipline": "run",
                    "estimated_duration_min": 60,
                    "target_intensity": "Zone 2 to Low Zone 3",
                    "description": "Comfortable steady distance run building into controlled marathon/tempo pace in final 15 minutes.",
                    "steps": [
                        {"type": "Warmup", "duration_min": 10, "target": "Easy Z1-Z2"},
                        {"type": "Aerobic Cruiser", "duration_min": 35, "target": "Solid Z2 Aerobic Base"},
                        {"type": "Finish Progression", "duration_min": 10, "target": "High Z2 / Low Z3 Race Feel"},
                        {"type": "Cooldown", "duration_min": 5, "target": "Walk & Stretch"},
                    ],
                }

        elif disc == "brick":
            return {
                "name": "Triathlon Brick: Race-Pace Bike to Run (75m)",
                "discipline": "brick",
                "estimated_duration_min": 75,
                "target_intensity": "Race Specific (70.3 / Olympic Intensity)",
                "description": "The quintessential triathlon session: 55m bike directly followed by a quick T2 transition and 20m off-the-bike run to adapt leg muscles.",
                "steps": [
                    {"type": "Bike Warmup", "duration_min": 10, "target": f"{int(ftp * 0.60)}W (Z2)", "cadence": "90 rpm"},
                    {"type": "Bike Main Effort", "duration_min": 40, "target": f"{int(ftp * 0.80)}-{int(ftp * 0.85)}W (Target Race Pace)", "cadence": "90-95 rpm"},
                    {"type": "Bike Spin-Out", "duration_min": 5, "target": "High cadence (98+ rpm) to prepare legs for running"},
                    {"type": "Transition 2 (T2)", "duration_min": 2, "target": "Quick shoe swap, hydrate"},
                    {"type": "Transition Run", "duration_min": 18, "target": "First 5 min slightly easier, settle into goal race pace"},
                ],
            }

        elif disc == "strength":
            return {
                "name": "Strength: Triathlon Stability & Posterior Chain (40m)",
                "discipline": "strength",
                "estimated_duration_min": 40,
                "target_intensity": "Core & Injury Prevention",
                "description": "Functional multi-sport strength: strengthens glutes, hamstrings, rotator cuffs, and core to prevent running overuse and swimming shoulder pain.",
                "steps": [
                    {"type": "Warmup", "description": "Hip openers, glute bridges, arm circles (5 min)"},
                    {"type": "Exercise 1", "name": "Bulgarian Split Squats", "sets": 3, "reps": 10, "rest": "60s"},
                    {"type": "Exercise 2", "name": "Romanian Deadlifts (Dumbbells)", "sets": 3, "reps": 10, "rest": "60s"},
                    {"type": "Exercise 3", "name": "Single-Arm Dumbbell Rows", "sets": 3, "reps": 12, "rest": "45s"},
                    {"type": "Exercise 4", "name": "Side Planks with Leg Lift", "sets": 3, "reps": "30s each side", "rest": "30s"},
                    {"type": "Exercise 5", "name": "Band Pull-Aparts & Y-T-W", "sets": 2, "reps": 15, "rest": "30s"},
                ],
            }

        # Fallback default
        return {
            "name": f"{discipline.capitalize()} Aerobic Session",
            "discipline": discipline,
            "estimated_duration_min": target_duration_min,
            "target_intensity": "Zone 2",
            "description": "Consistent aerobic maintenance workout.",
            "steps": [{"type": "Main", "duration_min": target_duration_min, "target": "Zone 2"}],
        }
