#!/bin/bash

set -m
source ~/.relinos/env/bin/activate

export $(cat ~/.relinos/config | xargs)

uvicorn relinos.browser_worker:app --host 0.0.0.0 --port 18765 --loop asyncio &
PID1=$!
uvicorn relinos.main:app --host 0.0.0.0 --port "${PORT:-8031}" --loop asyncio &
PID2=$!

trap 'kill -INT $PID1 $PID2 $PID3 2>/dev/null; wait' INT TERM
wait
