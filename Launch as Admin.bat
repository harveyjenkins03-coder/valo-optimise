@echo off
cd /d "%~dp0"
powershell -WindowStyle Hidden -Command "Start-Process pythonw -ArgumentList '\"%~dp0main.py\"' -Verb RunAs -WorkingDirectory '%~dp0'"
