// AI Triathlon Trainer Client Logic

document.addEventListener("DOMContentLoaded", () => {
  let selectedDiscipline = "bike";
  let currentWorkout = null;
  let readinessLevel = "PRIME";

  // Elements
  const authStatusBadge = document.getElementById("authStatusBadge");
  const authDot = document.getElementById("authDot");
  const authStatusText = document.getElementById("authStatusText");
  const openAuthModalBtn = document.getElementById("openAuthModalBtn");
  const closeAuthModalBtn = document.getElementById("closeAuthModalBtn");
  const authModal = document.getElementById("authModal");
  const checkAuthBtn = document.getElementById("checkAuthBtn");
  const copyAuthCmdBtn = document.getElementById("copyAuthCmdBtn");

  const coachHeadline = document.getElementById("coachHeadline");
  const coachAdvice = document.getElementById("coachAdvice");
  const readinessLevelBadge = document.getElementById("readinessLevelBadge");
  const readinessScoreVal = document.getElementById("readinessScoreVal");
  const readinessCircle = document.getElementById("readinessCircle");

  const sleepScoreVal = document.getElementById("sleepScoreVal");
  const sleepDurationVal = document.getElementById("sleepDurationVal");
  const sleepBreakdown = document.getElementById("sleepBreakdown");
  const hrvStatusVal = document.getElementById("hrvStatusVal");
  const hrvAvgVal = document.getElementById("hrvAvgVal");
  const bodyBatteryVal = document.getElementById("bodyBatteryVal");
  const batteryDrainVal = document.getElementById("batteryDrainVal");
  const restingHrVal = document.getElementById("restingHrVal");
  const stressVal = document.getElementById("stressVal");

  // Weekly Elements
  const swimDistance = document.getElementById("swimDistance");
  const swimHours = document.getElementById("swimHours");
  const swimSessions = document.getElementById("swimSessions");
  const swimProgressBar = document.getElementById("swimProgressBar");

  const bikeDistance = document.getElementById("bikeDistance");
  const bikeHours = document.getElementById("bikeHours");
  const bikeSessions = document.getElementById("bikeSessions");
  const bikeProgressBar = document.getElementById("bikeProgressBar");

  const runDistance = document.getElementById("runDistance");
  const runHours = document.getElementById("runHours");
  const runSessions = document.getElementById("runSessions");
  const runProgressBar = document.getElementById("runProgressBar");

  const strengthHours = document.getElementById("strengthHours");
  const strengthSessions = document.getElementById("strengthSessions");
  const strengthProgressBar = document.getElementById("strengthProgressBar");
  const brickSessions = document.getElementById("brickSessions");

  const weeklyTotalHours = document.getElementById("weeklyTotalHours");
  const weeklyTotalSessions = document.getElementById("weeklyTotalSessions");

  // Workout Elements
  const workoutTypeSelect = document.getElementById("workoutTypeSelect");
  const workoutDurationInput = document.getElementById("workoutDurationInput");
  const generateWorkoutBtn = document.getElementById("generateWorkoutBtn");
  const workoutCard = document.getElementById("workoutCard");
  const workoutTitle = document.getElementById("workoutTitle");
  const workoutDesc = document.getElementById("workoutDesc");
  const workoutIntensityBadge = document.getElementById("workoutIntensityBadge");
  const workoutDurationBadge = document.getElementById("workoutDurationBadge");
  const workoutStepsContainer = document.getElementById("workoutStepsContainer");
  const pushToGarminBtn = document.getElementById("pushToGarminBtn");
  const scheduleDateInput = document.getElementById("scheduleDateInput");
  const refreshActivitiesBtn = document.getElementById("refreshActivitiesBtn");
  const activitiesTableBody = document.getElementById("activitiesTableBody");

  // Preset today's date for scheduling
  const today = new Date().toISOString().split("T")[0];
  if (scheduleDateInput) scheduleDateInput.value = today;

  // Options map by discipline
  const workoutOptionsMap = {
    bike: [
      { value: "sweetspot", label: "80/20 Sweet Spot 3x12m (Cycling)" },
      { value: "endurance", label: "Zone 2 Aerobic Base (60-90m)" },
      { value: "vo2max", label: "VO2 Max 3-min Intervals" },
      { value: "recovery", label: "Active Recovery Spin (45m)" },
    ],
    swim: [
      { value: "threshold", label: "CSS Threshold Ladder (2500m)" },
      { value: "technique", label: "Technique, Catch Drills & Pull (1500m)" },
      { value: "endurance", label: "Aerobic Continuous Pace" },
    ],
    run: [
      { value: "intervals", label: "5x1km Lactate Threshold Repeats" },
      { value: "endurance", label: "Progressive Aerobic Long Run" },
      { value: "shakeout", label: "Zone 2 Recovery Shakeout (30m)" },
    ],
    brick: [
      { value: "race_brick", label: "Race-Pace Bike (45m) + Off-the-Bike Run (20m)" },
      { value: "threshold_brick", label: "Threshold Bike + Transition 5k" },
    ],
    strength: [
      { value: "stability", label: "Triathlon Stability & Posterior Chain" },
      { value: "core", label: "Core & Rotator Cuff Shoulder Health" },
    ],
  };

  function updateWorkoutOptions(disc) {
    const options = workoutOptionsMap[disc] || workoutOptionsMap.bike;
    workoutTypeSelect.innerHTML = "";
    options.forEach((opt) => {
      const el = document.createElement("option");
      el.value = opt.value;
      el.textContent = opt.label;
      workoutTypeSelect.appendChild(el);
    });
  }

  // Discipline selection
  document.querySelectorAll(".disc-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".disc-btn").forEach((b) => {
        b.classList.remove("active-disc");
        b.className = "disc-btn px-4 py-2 rounded-xl text-xs font-semibold bg-slate-800 text-slate-300 hover:text-white border border-slate-700/80 transition-all";
      });
      btn.className = "disc-btn px-4 py-2 rounded-xl text-xs font-semibold bg-emerald-500 text-slate-950 border border-emerald-400 transition-all active-disc";
      selectedDiscipline = btn.dataset.disc;
      updateWorkoutOptions(selectedDiscipline);
    });
  });

  // Modal open / close
  openAuthModalBtn.addEventListener("click", () => authModal.classList.remove("hidden"));
  closeAuthModalBtn.addEventListener("click", () => authModal.classList.add("hidden"));
  authModal.addEventListener("click", (e) => {
    if (e.target === authModal) authModal.classList.add("hidden");
  });

  // Copy Auth command
  copyAuthCmdBtn.addEventListener("click", () => {
    const cmd = "/Users/kachkarda/.local/bin/uvx --python 3.12 --from git+https://github.com/Taxuspt/garmin_mcp garmin-mcp-auth";
    navigator.clipboard.writeText(cmd).then(() => {
      copyAuthCmdBtn.textContent = "Copied!";
      setTimeout(() => (copyAuthCmdBtn.textContent = "Copy"), 2000);
    });
  });

  // Check auth
  async function checkAuth() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      if (data.authenticated) {
        authDot.className = "w-2 h-2 rounded-full bg-emerald-400";
        authStatusText.textContent = `Connected: ${data.user || "Garmin"}`;
        authStatusBadge.className = "flex items-center space-x-2 px-3 py-1.5 rounded-full border border-emerald-800/80 bg-emerald-950/40 text-xs font-semibold text-emerald-400";
      } else {
        authDot.className = "w-2 h-2 rounded-full bg-amber-400 animate-pulse";
        authStatusText.textContent = "Demo Mode (Not Authenticated)";
        authStatusBadge.className = "flex items-center space-x-2 px-3 py-1.5 rounded-full border border-amber-800/80 bg-amber-950/40 text-xs font-semibold text-amber-400";
      }
    } catch (e) {
      authStatusText.textContent = "Offline";
    }
  }

  checkAuthBtn.addEventListener("click", async () => {
    checkAuthBtn.textContent = "Verifying...";
    await checkAuth();
    await loadReadiness();
    await loadWeeklySummary();
    await loadActivities();
    checkAuthBtn.textContent = "Verify Connection Status";
    setTimeout(() => authModal.classList.add("hidden"), 800);
  });

  // Load Readiness
  async function loadReadiness() {
    try {
      const res = await fetch("/api/readiness");
      const data = await res.json();
      const m = data.metrics || {};
      const coach = data.coach_assessment || {};

      readinessLevel = coach.level || "PRIME";

      // Coach Dispatch
      coachHeadline.textContent = coach.headline || "Ready for training";
      coachAdvice.textContent = coach.advice || "";
      readinessLevelBadge.textContent = coach.level || "Optimal";
      readinessLevelBadge.className = `inline-flex items-center px-2.5 py-0.5 rounded-md text-xs font-semibold tracking-wide uppercase ${
        coach.badge_color === "emerald"
          ? "bg-emerald-950/80 text-emerald-400 border border-emerald-800/60"
          : coach.badge_color === "amber"
          ? "bg-amber-950/80 text-amber-400 border border-amber-800/60"
          : "bg-rose-950/80 text-rose-400 border border-rose-800/60"
      }`;

      // Score and Circular Meter (Circumference = 2 * PI * 52 ≈ 326.7)
      const score = coach.score || 75;
      readinessScoreVal.textContent = score;
      const circumference = 326.7;
      const offset = circumference - (score / 100) * circumference;
      readinessCircle.style.strokeDashoffset = offset;
      readinessCircle.setAttribute(
        "class",
        score >= 75 ? "text-emerald-400 transition-all duration-1000" : score >= 50 ? "text-amber-400 transition-all duration-1000" : "text-rose-400 transition-all duration-1000"
      );

      // Sleep
      sleepScoreVal.textContent = m.sleep_score ?? "--";
      sleepDurationVal.textContent = m.sleep_duration_hours ? `(${m.sleep_duration_hours} hrs)` : "";
      if (m.deep_sleep_hours || m.rem_sleep_hours) {
        sleepBreakdown.textContent = `Deep: ${m.deep_sleep_hours || 0}h · REM: ${m.rem_sleep_hours || 0}h`;
      }

      // HRV
      hrvStatusVal.textContent = m.hrv_status || "Balanced";
      hrvAvgVal.textContent = m.hrv_weekly_avg ? `7d Avg: ${m.hrv_weekly_avg} ms` : `Last night: ${m.hrv_last_night_avg || "--"} ms`;

      // Body Battery
      bodyBatteryVal.textContent = m.body_battery_current ?? "--";
      if (m.body_battery_charged !== null && m.body_battery_drained !== null) {
        batteryDrainVal.textContent = `+${m.body_battery_charged || 0} / -${m.body_battery_drained || 0}`;
      }

      // Resting HR & Stress
      restingHrVal.textContent = m.resting_hr ?? "--";
      stressVal.textContent = m.stress_avg !== null ? `Stress: ${m.stress_avg} avg` : "Stress: normal";
    } catch (e) {
      console.error("Error loading readiness", e);
    }
  }

  // Load Weekly Summary
  async function loadWeeklySummary() {
    try {
      const res = await fetch("/api/weekly-summary");
      const summary = await res.json();
      const disc = summary.disciplines || {};

      // Swim
      const sw = disc.swim || {};
      swimDistance.textContent = sw.distance_km !== undefined ? `${sw.distance_km}k` : "--";
      swimHours.textContent = `${sw.duration_hours || 0} hrs logged`;
      swimSessions.textContent = `${sw.sessions || 0} sessions`;
      const swimPct = Math.min(100, Math.round(((sw.distance_km || 0) / (sw.target_km || 4.0)) * 100));
      swimProgressBar.style.width = `${swimPct}%`;

      // Bike
      const bk = disc.bike || {};
      bikeDistance.textContent = bk.distance_km !== undefined ? `${bk.distance_km}k` : "--";
      bikeHours.textContent = `${bk.duration_hours || 0} hrs logged`;
      bikeSessions.textContent = `${bk.sessions || 0} sessions`;
      const bikePct = Math.min(100, Math.round(((bk.distance_km || 0) / (bk.target_km || 80.0)) * 100));
      bikeProgressBar.style.width = `${bikePct}%`;

      // Run
      const rn = disc.run || {};
      runDistance.textContent = rn.distance_km !== undefined ? `${rn.distance_km}k` : "--";
      runHours.textContent = `${rn.duration_hours || 0} hrs logged`;
      runSessions.textContent = `${rn.sessions || 0} sessions`;
      const runPct = Math.min(100, Math.round(((rn.distance_km || 0) / (rn.target_km || 25.0)) * 100));
      runProgressBar.style.width = `${runPct}%`;

      // Strength & Brick
      const st = disc.strength || {};
      const br = disc.brick || {};
      strengthHours.textContent = `${st.duration_hours || 0}h`;
      strengthSessions.textContent = `${st.sessions || 0} sessions logged`;
      brickSessions.textContent = `${br.sessions || 0} bricks`;
      const stPct = Math.min(100, Math.round(((st.duration_hours || 0) / 1.5) * 100));
      strengthProgressBar.style.width = `${stPct}%`;

      // Totals
      weeklyTotalHours.textContent = summary.total_duration_hours || "0";
      weeklyTotalSessions.textContent = summary.total_sessions || "0";
    } catch (e) {
      console.error("Error loading weekly summary", e);
    }
  }

  // Load Activities Table
  async function loadActivities() {
    try {
      const res = await fetch("/api/activities?limit=15");
      const data = await res.json();
      const list = data.activities || [];

      if (!list.length) {
        activitiesTableBody.innerHTML = `<tr><td colspan="8" class="py-6 text-center text-slate-500">No activities found in Garmin Connect yet.</td></tr>`;
        return;
      }

      activitiesTableBody.innerHTML = list
        .map((act) => {
          const disc = act.discipline || "other";
          let badgeClass = "badge-other";
          let discIcon = "🏃";
          if (disc === "swim") {
            badgeClass = "badge-swim";
            discIcon = "🏊 Swim";
          } else if (disc === "bike") {
            badgeClass = "badge-bike";
            discIcon = "🚴 Bike";
          } else if (disc === "run") {
            badgeClass = "badge-run";
            discIcon = "🏃 Run";
          } else if (disc === "brick") {
            badgeClass = "badge-brick";
            discIcon = "🧱 Brick";
          } else if (disc === "strength") {
            badgeClass = "badge-strength";
            discIcon = "🏋️ Strength";
          }

          const dateStr = act.start_time ? act.start_time.split("T")[0] : "--";
          const distStr = act.distance_km ? `${act.distance_km} km` : "--";
          const durStr = act.duration_min ? `${act.duration_min} min` : "--";
          const paceStr = act.pace_str || (act.avg_power ? `${act.avg_power}W` : "--");
          const hrStr = act.avg_hr ? `${act.avg_hr} bpm` : "--";
          const teStr = act.aerobic_te ? `Aero: ${act.aerobic_te} · Ana: ${act.anaerobic_te || 0}` : "--";

          return `
            <tr class="hover:bg-slate-800/40 transition-colors">
              <td class="py-3 px-4">
                <span class="inline-flex items-center px-2 py-0.5 rounded-full text-[10px] font-semibold ${badgeClass}">
                  ${discIcon}
                </span>
              </td>
              <td class="py-3 px-4 font-medium text-white">${act.name}</td>
              <td class="py-3 px-4 text-slate-400 font-mono text-[11px]">${dateStr}</td>
              <td class="py-3 px-4 font-semibold text-slate-200">${distStr}</td>
              <td class="py-3 px-4 text-slate-300">${durStr}</td>
              <td class="py-3 px-4 font-mono text-cyan-400">${paceStr}</td>
              <td class="py-3 px-4 text-rose-300">${hrStr}</td>
              <td class="py-3 px-4 text-slate-400 text-[11px]">${teStr}</td>
            </tr>
          `;
        })
        .join("");
    } catch (e) {
      console.error("Error loading activities", e);
    }
  }

  // Generate Workout
  generateWorkoutBtn.addEventListener("click", async () => {
    generateWorkoutBtn.disabled = true;
    generateWorkoutBtn.innerHTML = `<span>Generating...</span>`;

    try {
      const type = workoutTypeSelect.value;
      const duration = parseInt(workoutDurationInput.value, 10) || 60;

      const res = await fetch("/api/workouts/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          discipline: selectedDiscipline,
          workout_type: type,
          readiness_level: readinessLevel,
          target_duration_min: duration,
        }),
      });

      const data = await res.json();
      currentWorkout = data.workout;

      workoutTitle.textContent = currentWorkout.name;
      workoutDesc.textContent = currentWorkout.description;
      workoutIntensityBadge.textContent = currentWorkout.target_intensity;
      workoutDurationBadge.textContent = `${currentWorkout.estimated_duration_min} min`;

      // Render Steps
      workoutStepsContainer.innerHTML = (currentWorkout.steps || [])
        .map(
          (s, idx) => `
          <div class="bg-slate-900 border border-slate-800/80 p-3 rounded-lg flex items-center justify-between text-xs">
            <div class="flex items-center space-x-3">
              <span class="w-6 h-6 rounded-md bg-slate-800 text-slate-300 flex items-center justify-center font-bold text-[11px]">${idx + 1}</span>
              <div>
                <span class="font-bold text-white">${s.type || s.name || "Step"}</span>
                <p class="text-slate-400 text-[11px] mt-0.5">${s.description || s.target || ""}</p>
              </div>
            </div>
            <div class="text-right">
              <span class="font-mono text-emerald-400 font-semibold">${s.duration_min ? s.duration_min + 'm' : (s.distance_m ? s.distance_m + 'm' : (s.sets ? s.sets + 'x' + s.reps : ''))}</span>
              ${s.cadence ? `<div class="text-[10px] text-slate-400">${s.cadence}</div>` : ''}
              ${s.recovery ? `<div class="text-[10px] text-amber-400">Rest: ${s.recovery}</div>` : ''}
            </div>
          </div>
        `
        )
        .join("");

      workoutCard.classList.remove("hidden");
    } catch (e) {
      alert("Failed to generate workout: " + e);
    } finally {
      generateWorkoutBtn.disabled = false;
      generateWorkoutBtn.innerHTML = `<span>⚡ Generate Tailored Workout</span>`;
    }
  });

  // Push to Garmin
  pushToGarminBtn.addEventListener("click", async () => {
    if (!currentWorkout) return;
    pushToGarminBtn.disabled = true;
    pushToGarminBtn.innerHTML = `<span>Pushing to Garmin...</span>`;

    try {
      const res = await fetch("/api/workouts/push", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          workout: currentWorkout,
          target_date: scheduleDateInput.value,
        }),
      });

      const data = await res.json();
      alert(`Garmin Sync: ${data.message}`);
    } catch (e) {
      alert("Error pushing to Garmin: " + e);
    } finally {
      pushToGarminBtn.disabled = false;
      pushToGarminBtn.innerHTML = `<span>⌚ Push to Garmin Watch</span>`;
    }
  });

  refreshActivitiesBtn.addEventListener("click", () => {
    loadActivities();
    loadWeeklySummary();
  });

  // Init
  updateWorkoutOptions("bike");
  checkAuth();
  loadReadiness();
  loadWeeklySummary();
  loadActivities();
});
