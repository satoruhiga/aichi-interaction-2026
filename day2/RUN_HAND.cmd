@echo off
cd /d "%~dp0.."
pixi run --locked python -m day2.scripts.hand %*
if errorlevel 1 pause
