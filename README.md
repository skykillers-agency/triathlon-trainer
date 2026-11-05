# AI Triathlon Trainer

An AI-powered multi-sport coaching and training management dashboard connecting directly to your Garmin Connect account via [taxuspt/garmin_mcp](https://github.com/taxuspt/garmin_mcp).

## Features
- **Garmin Connect Integration**: Connects via OAuth tokens in `~/.garminconnect` (no password stored).
- **Daily Recovery & Readiness Scoreboard**: Analyzes Sleep stages, overnight HRV, Body Battery, and Resting HR.
- **Dynamic Training Prescription**: Flags high-intensity vs aerobic vs active recovery days based on autonomic nervous system recovery.
- **Discipline Volume Tracking**: Weekly distance & time targets for Swim, Bike, Run, Strength, and Brick sessions.
- **Adaptive AI Workout Planner**: Generates structured workouts (CSS swim ladders, sweet-spot intervals, 5x1k threshold repeats, brick bike-to-run transitions) and pushes them to your Garmin watch calendar.
- **Garmin MCP Server**: Direct tool integration with Antigravity / Claude for in-chat coaching.

## Quick Start

### 1. Authenticate with Garmin Connect
Run the one-time authentication script to generate your OAuth tokens:
```bash
./authenticate_garmin.sh
```

### 2. Launch the Trainer Dashboard
```bash
cd triathlon_trainer
./run.sh
```
Then open [http://localhost:8000](http://localhost:8000) in your browser.
