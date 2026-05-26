@echo off
echo [VoidCraft] Starting Flask portal...
start "Flask Portal" python main.py
timeout /t 2 >nul
echo [VoidCraft] Starting Discord bot...
start "Discord Bot" python bot.py
echo [VoidCraft] Both services running.
echo Portal: http://127.0.0.1:5000
pause
