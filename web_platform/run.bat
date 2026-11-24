@echo off
chcp 65001 > nul
title BotCraft Web Platform & Workspace

echo Starting BotCraft Web Platform...
echo Python: ..\prompt_shop_bot\venv\Scripts\python.exe

"..\prompt_shop_bot\venv\Scripts\python.exe" server.py
pause
