@echo off
REM Wrapper para el Programador de tareas de Windows (ejecucion semanal).
cd /d "%~dp0"
if not exist logs mkdir logs
".venv\Scripts\python.exe" run_obsolescencia.py >> logs\obsolescencia.log 2>&1
