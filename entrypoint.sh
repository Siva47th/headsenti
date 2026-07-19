#!/bin/sh

# Start the python scheduler in the background and redirect output to a log file
python -u src/scheduler.py > scheduler.log 2>&1 &

# Start the FastAPI server in the foreground on port 7860 (required by Hugging Face)
python -m uvicorn src.api:app --host 0.0.0.0 --port 7860
