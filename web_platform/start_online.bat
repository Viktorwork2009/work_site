@echo off
chcp 65001 > nul
title BotCraft Web Platform + Public Online Tunnel

echo =======================================================
echo    1. ЗАПУСК ВЕБ-СЕРВЕРА BOTCRAFT (ПОРТ 8080)
echo =======================================================

start "BotCraft Server" cmd /k "chcp 65001 > nul && title BotCraft Server && ..\prompt_shop_bot\venv\Scripts\python.exe server.py"

timeout /t 2 /nobreak > nul

echo.
echo =======================================================
echo    2. ПОЛУЧЕНИЕ ПУБЛИЧНОЙ HTTPS ССЫЛКИ ДЛЯ КЛИЕНТОВ
echo =======================================================
echo Подключение к безопасному туннелю localhost.run...
echo В появившихся строках ниже найдите адрес с https://
echo Эту ссылку можно отправлять клиентам на Авито!
echo =======================================================
echo.

ssh -R 80:localhost:8080 nokey@localhost.run

pause
