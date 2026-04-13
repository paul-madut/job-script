#!/bin/bash
# Job Cannon - Autonomous run script
# Used by cron/launchd to trigger the pipeline.
#
# Setup:
#   chmod +x run.sh
#
# Manual cron (every day at 9am):
#   crontab -e
#   0 9 * * * /Users/paulmadut/Desktop/Projects/job-script/run.sh
#
# Or use the included launchd plist (see below).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Activate venv if it exists
if [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
elif [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
fi

# Run the full pipeline
python -m src.orchestrator run 2>&1 | tee -a output/logs/run_$(date +%Y%m%d_%H%M%S).log
