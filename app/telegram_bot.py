"""AI Triathlon Coach — Telegram Bot.

Provides a full command interface and automatic updates via Telegram.

Commands:
    /start          - Register chat & show welcome
    /readiness      - Today's HRV, Body Battery, sleep & readiness score
    /workout        - AI workout recommendation for today
    /activities     - Last 5 Garmin activities
    /weekly         - This week's training load summary
    /coach <msg>    - Ask the AI coach anything
    /briefing HH:MM - Set daily morning briefing time (default 07:00)
    /help           - Show all commands
"""

from __future__ import annotations

import asyncio
import logging
import os
from datetime import date, datetime, time as dtime, timedelta
from typing import Optional

from telegram import BotCommand, Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .coach_engine import CoachEngine
from .garmin_client import GarminClient

logger = logging.getLogger("telegram_bot")

# ── Token & persistence ────────────────────────────────────────────────────────
TELEGRAM_TOKEN = os.environ.get(
    "TELEGRAM_BOT_TOKEN", "9050593562:AAFNIMWsUmob4rs58Qi8MJ996t43aqqKGWI"
)
DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".bot_data")
os.makedirs(DATA_DIR, exist_ok=True)

CHAT_ID_FILE = os.path.join(DATA_DIR, "chatid.txt")
BRIEFING_TIME_FILE = os.path.join(DATA_DIR, "briefing.txt")
SEEN_ACTIVITIES_FILE = os.path.join(DATA_DIR, "seen_activities.txt")
DEFAULT_BRIEFING_HOUR = 6
DEFAULT_BRIEFING_MIN = 30

# ── Shared clients & coaching helpers ──────────────────────────────────────────
_garmin = GarminClient()


def _assess_readiness(raw: dict) -> dict:
    return CoachEngine.calculate_readiness_score(raw)


def _generate_workout(assessment: dict, activities: list) -> dict:
    level = assessment.get("level", "PRIME")
    past_discs = [a["discipline"] for a in activities if a.get("discipline") in ("swim", "bike", "run")]
    last = past_discs[0] if past_discs else "bike"
    next_disc = {"bike": "run", "run": "swim", "swim": "bike"}.get(last, "bike")
    w_type = "intervals" if level == "PRIME" else "endurance"
    return CoachEngine.generate_workout(
        discipline=next_disc,
        workout_type=w_type,
        readiness_level=level,
        target_duration_min=60,
    )


# ── Persistence helpers ────────────────────────────────────────────────────────

def save_chat_id(chat_id: int) -> None:
    with open(CHAT_ID_FILE, "w") as f:
        f.write(str(chat_id))


def load_chat_id() -> Optional[int]:
    try:
        with open(CHAT_ID_FILE) as f:
            return int(f.read().strip())
    except Exception:
        return None


def save_briefing_time(hour: int, minute: int) -> None:
    with open(BRIEFING_TIME_FILE, "w") as f:
        f.write(f"{hour}:{minute}")


def load_briefing_time() -> tuple[int, int]:
    try:
        with open(BRIEFING_TIME_FILE) as f:
            h, m = f.read().strip().split(":")
            return int(h), int(m)
    except Exception:
        return DEFAULT_BRIEFING_HOUR, DEFAULT_BRIEFING_MIN


def load_seen_activities() -> set[int]:
    try:
        with open(SEEN_ACTIVITIES_FILE) as f:
            return {int(x) for x in f.read().split() if x}
    except Exception:
        return set()


def save_seen_activities(ids: set[int]) -> None:
    with open(SEEN_ACTIVITIES_FILE, "w") as f:
        f.write("\n".join(str(i) for i in ids))


# ── Formatting helpers ─────────────────────────────────────────────────────────

def _readiness_badge(score: int) -> str:
    if score >= 75:
        return "🟢"
    if score >= 50:
        return "🟡"
    return "🔴"


def _discipline_emoji(disc: str) -> str:
    return {"swim": "🏊", "bike": "🚴", "run": "🏃", "strength": "💪", "brick": "🧱"}.get(disc, "🏅")


def _build_readiness_message(metrics: dict, assessment: dict) -> str:
    score = assessment.get("score", 0)
    level = assessment.get("level", "UNKNOWN")
    badge = _readiness_badge(score)
    headline = assessment.get("headline", "")
    advice = assessment.get("advice", "")

    sleep_score = metrics.get("sleep_score")
    sleep_hrs = metrics.get("sleep_duration_hours")
    hrv_status = metrics.get("hrv_status", "UNKNOWN")
    hrv_avg = metrics.get("hrv_last_night_avg")
    bb = metrics.get("body_battery_current") or metrics.get("body_battery_charged")
    rhr = metrics.get("resting_hr")
    stress = metrics.get("stress_avg")
    today = metrics.get("date", date.today().isoformat())

    lines = [
        f"*📊 Readiness Report — {today}*",
        "",
        f"{badge} *{score}/100 — {level}*",
        f"_{headline}_",
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        f"😴 Sleep: {f'{sleep_score}/100' if sleep_score else 'N/A'}  ({f'{sleep_hrs}h' if sleep_hrs else '?'})",
        f"💓 HRV: {hrv_status}{f'  ({hrv_avg} ms)' if hrv_avg else ''}",
        f"⚡ Body Battery: {bb if bb else 'N/A'}",
        f"❤️  Resting HR: {f'{rhr} bpm' if rhr else 'N/A'}",
        f"😰 Avg Stress: {stress if stress else 'N/A'}",
        "━━━━━━━━━━━━━━━━━━━━",
        "",
        f"💬 _{advice}_",
    ]
    return "\n".join(lines)


def _build_workout_message(workout: dict) -> str:
    disc = workout.get("discipline", "bike")
    emoji = _discipline_emoji(disc)
    name = workout.get("name", "Workout")
    duration = workout.get("estimated_duration_min") or workout.get("duration_min", 60)
    intensity = workout.get("target_intensity") or workout.get("intensity_label", "Moderate")
    desc = workout.get("description", "")

    steps = workout.get("steps", [])
    step_lines = []
    for s in steps:
        step_type = s.get("type") or s.get("name", "Step")
        dur_str = f"{s['duration_min']}m" if s.get("duration_min") else (f"{s['distance_m']}m" if s.get("distance_m") else "")
        target_str = s.get("target") or s.get("description", "")
        line = f"  • *{step_type}*"
        if dur_str:
            line += f" ({dur_str})"
        if target_str:
            line += f": {target_str}"
        step_lines.append(line)

    lines = [
        f"{emoji} *Today's Recommended Workout*",
        "",
        f"*{name}*",
        f"⏱ Duration: {duration} min  |  🎯 Intensity: {intensity}",
        "",
        f"_{desc}_",
    ]
    if step_lines:
        lines += ["", "📋 *Structure:*"] + step_lines

    lines += [
        "",
        "━━━━━━━━━━━━━━━━━━━━",
        "💡 Use /readiness to check today's recovery before starting.",
    ]
    return "\n".join(lines)


def _build_activities_message(activities: list[dict]) -> str:
    if not activities:
        return "📭 No recent activities found."

    lines = ["*🏅 Recent Activities*", ""]
    for a in activities[:5]:
        emoji = _discipline_emoji(a["discipline"])
        dist = f"{a['distance_km']} km" if a["distance_km"] > 0 else ""
        dur = f"{a['duration_min']} min"
        hr = f"HR {a['avg_hr']} bpm" if a.get("avg_hr") else ""
        pwr = f"⚡{a['avg_power']}W" if a.get("avg_power") else ""
        pace = a.get("pace_str", "")
        date_str = a["start_time"][:10]

        meta = "  |  ".join(filter(None, [dist, dur, hr, pwr, pace]))
        lines.append(f"{emoji} *{a['name']}*  `{date_str}`")
        lines.append(f"   {meta}")
        lines.append("")

    return "\n".join(lines)


def _build_weekly_message(summary: dict) -> str:
    discs = summary.get("disciplines", {})
    week_start = summary.get("week_start", "")
    total_hrs = summary.get("total_duration_hours", 0)
    total_sessions = summary.get("total_sessions", 0)

    lines = [
        f"*📅 Week of {week_start}*",
        f"Total: *{total_hrs}h* across *{total_sessions} sessions*",
        "",
    ]

    emoji_map = {"swim": "🏊", "bike": "🚴", "run": "🏃", "strength": "💪", "brick": "🧱"}
    for disc, data in discs.items():
        if data.get("sessions", 0) == 0:
            continue
        e = emoji_map.get(disc, "🏅")
        dist = f"{data['distance_km']} km" if data.get("distance_km") else ""
        hrs = f"{data['duration_hours']}h"
        target_km = data.get("target_km")
        target_hrs = data.get("target_hours")

        if target_km:
            pct = int(data.get("distance_km", 0) / target_km * 100)
            target_str = f"target: {target_km}km ({pct}%)"
        elif target_hrs:
            pct = int(data.get("duration_hours", 0) / target_hrs * 100)
            target_str = f"target: {target_hrs}h ({pct}%)"
        else:
            target_str = ""

        meta = "  |  ".join(filter(None, [dist, hrs, target_str]))
        lines.append(f"{e} *{disc.capitalize()}* — {meta}")

    return "\n".join(lines)


def _build_new_activity_message(activity: dict) -> str:
    disc = activity["discipline"]
    emoji = _discipline_emoji(disc)
    name = activity["name"]
    dist = f"{activity['distance_km']} km" if activity["distance_km"] > 0 else ""
    dur = f"{activity['duration_min']} min"
    hr = f"HR avg {activity['avg_hr']} bpm" if activity.get("avg_hr") else ""
    pwr = f"Avg Power {activity['avg_power']}W  |  NP {activity.get('normalized_power', '?')}W" if activity.get("avg_power") else ""
    pace = activity.get("pace_str", "")
    te = activity.get("aerobic_te")
    te_str = f"Aerobic TE: {te:.1f}" if te else ""

    meta = "\n".join(filter(None, [
        f"📏 {dist}" if dist else "",
        f"⏱ {dur}",
        f"❤️  {hr}" if hr else "",
        f"⚡ {pwr}" if pwr else "",
        f"🏃 Pace: {pace}" if pace else "",
        f"📈 {te_str}" if te_str else "",
    ]))

    # Simple recovery advice based on training effect
    if te and te >= 4.0:
        recovery = "💤 *High load* — prioritise 8h sleep tonight and an easy day tomorrow."
    elif te and te >= 3.0:
        recovery = "😴 *Good stimulus* — eat well, hydrate, and get 7-8h sleep."
    else:
        recovery = "✅ *Light session* — you're good to train again tomorrow."

    return (
        f"{emoji} *New Activity Synced!*\n\n"
        f"*{name}*\n"
        f"{meta}\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n"
        f"{recovery}"
    )


def _build_scheduled_message(items: list[dict]) -> str:
    if not items:
        return (
            "📭 *No workouts currently scheduled on your Garmin calendar.*\n\n"
            "💡 You can generate and push one anytime with the AI Coach!"
        )

    lines = ["*🗓 Scheduled Garmin Workouts*", ""]
    today = date.today()
    for item in items:
        emoji = _discipline_emoji(item["discipline"])
        d_str = item["date"]
        try:
            d_obj = date.fromisoformat(d_str[:10])
            if d_obj == today:
                rel = "Today"
            elif d_obj == today + timedelta(days=1):
                rel = "Tomorrow"
            else:
                rel = d_obj.strftime("%A, %b %d")
        except Exception:
            rel = d_str

        lines.append(f"{emoji} *{item['title']}*")
        lines.append(f"   📅 `{d_str}` ({rel})  |  Sport: {item['sport_type'].capitalize()}")
        lines.append("")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("💡 Open Garmin Connect or your Epix Pro to sync and ride/run.")
    return "\n".join(lines)


# ── Command handlers ───────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = update.effective_chat.id
    save_chat_id(chat_id)
    name = update.effective_user.first_name or "Athlete"
    h, m = load_briefing_time()

    text = (
        f"🏊🚴🏃 *Welcome, {name}!* Your AI Triathlon Coach is live!\n\n"
        "Here's what I can do:\n\n"
        "📊 /readiness — Today's recovery metrics\n"
        "🎯 /workout — AI workout recommendation\n"
        "🗓 /scheduled — View scheduled Garmin workouts\n"
        "🏅 /activities — Last 5 Garmin activities\n"
        "📅 /weekly — This week's training load\n"
        "🤖 /coach \\[question\\] — Ask me anything\n"
        "⏰ /briefing HH:MM — Set morning briefing time\n"
        "❓ /help — Show this menu\n\n"
        f"🌅 I'll send you a morning briefing every day at *{h:02d}:{m:02d}*.\n"
        "You'll also get notified whenever a new activity syncs to Garmin! 🎉"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await cmd_start(update, context)


async def cmd_readiness(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Fetching your Garmin data...")
    try:
        raw = _garmin.get_today_readiness()
        assessment = _assess_readiness(raw)
        text = _build_readiness_message(raw, assessment)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Readiness error: {e}")
        await update.message.reply_text(f"❌ Could not fetch readiness data: {e}")


async def cmd_workout(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("🧠 Analysing your data and generating a workout...")
    try:
        raw = _garmin.get_today_readiness()
        assessment = _assess_readiness(raw)
        activities = _garmin.get_triathlon_activities(limit=10)
        workout = _generate_workout(assessment, activities)
        text = _build_workout_message(workout)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Workout error: {e}")
        await update.message.reply_text(f"❌ Could not generate workout: {e}")


async def cmd_scheduled(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Checking your Garmin calendar...")
    try:
        items = _garmin.get_scheduled_workouts(days_ahead=14)
        text = _build_scheduled_message(items)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Scheduled error: {e}")
        await update.message.reply_text(f"❌ Could not fetch scheduled workouts: {e}")


async def cmd_activities(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Fetching activities...")
    try:
        acts = _garmin.get_triathlon_activities(limit=5)
        text = _build_activities_message(acts)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Activities error: {e}")
        await update.message.reply_text(f"❌ Could not fetch activities: {e}")


async def cmd_weekly(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("⏳ Fetching weekly summary...")
    try:
        summary = _garmin.get_weekly_summary()
        text = _build_weekly_message(summary)
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Weekly error: {e}")
        await update.message.reply_text(f"❌ Could not fetch weekly summary: {e}")


async def cmd_coach(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    question = " ".join(context.args) if context.args else ""
    if not question:
        await update.message.reply_text(
            "💬 Ask me anything! Example:\n"
            "`/coach Should I do intervals today?`\n"
            "`/coach How is my training balance?`\n"
            "`/coach What should I focus on this week?`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    await update.message.reply_text("🧠 Thinking...")
    try:
        raw = _garmin.get_today_readiness()
        assessment = _assess_readiness(raw)
        activities = _garmin.get_triathlon_activities(limit=10)
        weekly = _garmin.get_weekly_summary()

        # Build a contextual coaching response
        score = assessment.get("score", 50)
        level = assessment.get("level", "MODERATE")
        discs = weekly.get("disciplines", {})
        bike_km = discs.get("bike", {}).get("distance_km", 0)
        run_km = discs.get("run", {}).get("distance_km", 0)
        swim_km = discs.get("swim", {}).get("distance_km", 0)

        q_lower = question.lower()

        if any(w in q_lower for w in ["interval", "hard", "intense", "threshold", "vo2"]):
            if score >= 75:
                answer = (
                    f"✅ *Green light for intensity!* Your readiness is {score}/100 ({level}).\n\n"
                    "Your autonomic nervous system is recovered — go for it. "
                    "Aim for 3–5 min intervals at 106–115% FTP or 4×8 min at threshold (95–100% FTP).\n\n"
                    "💡 Make sure you're well fuelled (60–90g carbs/hr) and have slept 7h+ tonight after."
                )
            elif score >= 50:
                answer = (
                    f"🟡 *Proceed with caution.* Readiness is {score}/100 ({level}).\n\n"
                    "Consider dropping to Sweet Spot (88–93% FTP) instead of full VO2 max. "
                    "Full threshold sessions on a tired body risk overreaching."
                )
            else:
                answer = (
                    f"🔴 *Not today.* Readiness is only {score}/100 ({level}).\n\n"
                    "Your body is signalling fatigue. Replace intervals with a Zone 2 spin (56–75% FTP) "
                    "or a rest day. Quality > quantity."
                )
        elif any(w in q_lower for w in ["balance", "load", "volume", "week", "training"]):
            answer = (
                f"📊 *This week's load:*\n"
                f"🏊 Swim: {swim_km} km\n"
                f"🚴 Bike: {bike_km} km\n"
                f"🏃 Run: {run_km} km\n\n"
                f"Your readiness is {score}/100. "
            )
            if bike_km < 40:
                answer += "Bike volume is below target — aim for another ride this week. "
            if run_km < 15:
                answer += "Run volume is low — add a 30–45 min easy run. "
            if swim_km < 2:
                answer += "Swim is behind — a 1.5–2 km session would balance things. "
        elif any(w in q_lower for w in ["tomorrow", "next", "recover", "rest"]):
            last_act = activities[0] if activities else None
            if last_act:
                te = last_act.get("aerobic_te", 0) or 0
                if te >= 4.0:
                    answer = (
                        f"😴 *Rest or easy day recommended.* Your last session ({last_act['name']}) "
                        f"had a high training effect ({te:.1f}). Let your body absorb it.\n\n"
                        "If you must train, keep it Zone 1–2 for under 45 min."
                    )
                else:
                    answer = (
                        f"✅ *You're good to train tomorrow.* Last session had moderate load (TE {te:.1f}).\n\n"
                        f"Current readiness: {score}/100. Sleep well and you'll be ready. "
                        "Consider a swim or run to balance your weekly load."
                    )
            else:
                answer = f"Your readiness is {score}/100 — you should be ready to train tomorrow."
        else:
            # Generic coaching response
            answer = (
                f"🏅 *AI Coach Response*\n\n"
                f"Question: _{question}_\n\n"
                f"Current readiness: *{score}/100 ({level})*\n"
                f"This week: 🚴 {bike_km}km bike | 🏃 {run_km}km run | 🏊 {swim_km}km swim\n\n"
                f"{assessment.get('advice', '')}\n\n"
                "For more specific advice, try:\n"
                "• `/coach Should I do intervals today?`\n"
                "• `/coach How is my training balance?`\n"
                "• `/coach Should I rest tomorrow?`"
            )

        await update.message.reply_text(answer, parse_mode=ParseMode.MARKDOWN)

    except Exception as e:
        logger.error(f"Coach error: {e}")
        await update.message.reply_text(f"❌ Coach error: {e}")


async def cmd_briefing(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not context.args:
        h, m = load_briefing_time()
        await update.message.reply_text(
            f"⏰ Morning briefing is set to *{h:02d}:{m:02d}*.\n\n"
            "To change it: `/briefing 06:30`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    time_str = context.args[0]
    try:
        h, m = map(int, time_str.split(":"))
        assert 0 <= h <= 23 and 0 <= m <= 59
        save_briefing_time(h, m)

        # Reschedule the job
        jq = context.application.job_queue
        current_jobs = jq.get_jobs_by_name("morning_briefing")
        for job in current_jobs:
            job.schedule_removal()

        chat_id = update.effective_chat.id
        jq.run_daily(
            _morning_briefing_job,
            time=dtime(hour=h, minute=m),
            name="morning_briefing",
            chat_id=chat_id,
        )
        await update.message.reply_text(
            f"✅ Morning briefing updated to *{h:02d}:{m:02d}* 🌅",
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception:
        await update.message.reply_text(
            "❌ Invalid format. Use: `/briefing 07:00`",
            parse_mode=ParseMode.MARKDOWN,
        )


async def cmd_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        "❓ Unknown command. Send /help to see available commands."
    )


# ── Scheduled jobs ─────────────────────────────────────────────────────────────

async def _morning_briefing_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send morning readiness briefing to saved chat."""
    chat_id = context.job.chat_id or load_chat_id()
    if not chat_id:
        logger.warning("Morning briefing: no chat_id saved yet")
        return
    try:
        raw = _garmin.get_today_readiness()
        assessment = _assess_readiness(raw)
        activities = _garmin.get_triathlon_activities(limit=10)
        workout = _generate_workout(assessment, activities)

        text = (
            "🌅 *Good morning, Yurii! Here's your daily briefing.*\n\n"
            + _build_readiness_message(raw, assessment)
            + "\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
            + _build_workout_message(workout)
        )
        await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
    except Exception as e:
        logger.error(f"Morning briefing error: {e}")
        try:
            await context.bot.send_message(chat_id=chat_id, text=f"⚠️ Briefing error: {e}")
        except Exception:
            pass


async def _check_new_activities_job(context: ContextTypes.DEFAULT_TYPE) -> None:
    """Poll Garmin every 15 min for new activities and notify user."""
    chat_id = load_chat_id()
    if not chat_id:
        return
    try:
        seen = load_seen_activities()
        activities = _garmin.get_triathlon_activities(limit=10)

        new_ones = [a for a in activities if a["activity_id"] not in seen]
        if not new_ones:
            return

        for activity in reversed(new_ones):  # oldest first
            text = _build_new_activity_message(activity)
            await context.bot.send_message(chat_id=chat_id, text=text, parse_mode=ParseMode.MARKDOWN)
            seen.add(activity["activity_id"])

        save_seen_activities(seen)
    except Exception as e:
        logger.debug(f"Activity check error: {e}")


# ── App factory ────────────────────────────────────────────────────────────────

def build_application() -> Application:
    """Build and configure the Telegram bot Application."""
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .build()
    )

    # Register command handlers
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("readiness", cmd_readiness))
    app.add_handler(CommandHandler("workout", cmd_workout))
    app.add_handler(CommandHandler(["scheduled", "scheduled_workout", "scheduledworkout"], cmd_scheduled))
    app.add_handler(MessageHandler(filters.Regex(r"(?i)^(scheduled(\s+workout)?)$"), cmd_scheduled))
    app.add_handler(CommandHandler("activities", cmd_activities))
    app.add_handler(CommandHandler("weekly", cmd_weekly))
    app.add_handler(CommandHandler("coach", cmd_coach))
    app.add_handler(CommandHandler("briefing", cmd_briefing))
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))

    return app


async def run_bot() -> None:
    """Start the bot with polling + scheduled jobs. Runs forever."""
    app = build_application()

    # Seed seen activities on first run (don't notify for old ones)
    try:
        if not os.path.exists(SEEN_ACTIVITIES_FILE):
            acts = _garmin.get_triathlon_activities(limit=20)
            save_seen_activities({a["activity_id"] for a in acts})
            logger.info(f"Seeded {len(acts)} existing activities as seen")
    except Exception as e:
        logger.warning(f"Could not seed activities: {e}")

    # Set bot commands menu
    async with app:
        await app.bot.set_my_commands([
            BotCommand("readiness", "Today's recovery metrics"),
            BotCommand("workout", "AI workout recommendation"),
            BotCommand("scheduled", "View scheduled Garmin workouts"),
            BotCommand("scheduled_workout", "View scheduled Garmin workouts"),
            BotCommand("activities", "Last 5 Garmin activities"),
            BotCommand("weekly", "This week's training load"),
            BotCommand("coach", "Ask the AI coach anything"),
            BotCommand("briefing", "Set morning briefing time"),
            BotCommand("help", "Show all commands"),
        ])

        # Schedule morning briefing
        h, m = load_briefing_time()
        saved_chat_id = load_chat_id()
        if saved_chat_id:
            app.job_queue.run_daily(
                _morning_briefing_job,
                time=dtime(hour=h, minute=m),
                name="morning_briefing",
                chat_id=saved_chat_id,
            )
            logger.info(f"Morning briefing scheduled at {h:02d}:{m:02d} for chat {saved_chat_id}")

        # Poll for new Garmin activities every 15 minutes
        app.job_queue.run_repeating(
            _check_new_activities_job,
            interval=900,  # 15 minutes
            first=60,       # first check after 1 min
            name="activity_check",
        )

        logger.info("🤖 Telegram bot starting — polling for updates...")
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)

        # Run until interrupted
        try:
            await asyncio.Event().wait()
        finally:
            await app.updater.stop()
            await app.stop()
