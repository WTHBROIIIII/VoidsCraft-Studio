#!/bin/bash
echo "[VoidCraft] Starting Flask portal..."
python main.py &
sleep 2
echo "[VoidCraft] Starting Discord bot..."
python bot.py &
echo ""
echo "[VoidCraft] Both services running."
echo "Portal: http://127.0.0.1:5000"
wait
