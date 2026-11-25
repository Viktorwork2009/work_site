@echo off
title BotCraft Web Platform CRM
echo Starting BotCraft Web Platform...
if exist "..\prompt_shop_bot\venv\Scripts\python.exe" (
    "..\prompt_shop_bot\venv\Scripts\python.exe" server.py
) else (
    python server.py
)
pause
