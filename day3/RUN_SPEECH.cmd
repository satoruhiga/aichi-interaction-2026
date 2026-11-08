@echo off
cd /d "%~dp0.."
pixi run --locked python -m day3.scripts.speech %*
if errorlevel 1 pause
