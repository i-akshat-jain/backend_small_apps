#!/bin/bash

echo "Killing any process on port 8000..."
lsof -ti tcp:8000 | xargs kill -9 2>/dev/null || true

echo "Starting backend..."
python main.py