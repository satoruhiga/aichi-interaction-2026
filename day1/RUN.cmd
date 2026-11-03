@echo off
cd /d "%~dp0.."
pixi run --locked python -m day1.main
if errorlevel 1 pause
