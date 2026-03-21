@echo off
title Valo Optimise Workspace
cd /d "%~dp0.."
pip install flask flask-socketio --quiet
echo.
echo  Starting Valo Optimise Workspace...
echo  Open http://localhost:5000 in your browser
echo.
echo  To share with your friend:
echo  1. Install ngrok: https://ngrok.com/download
echo  2. Run: ngrok http 5000
echo  3. Share the https://xxxx.ngrok.io URL with your friend
echo.
python workspace/server.py
pause
