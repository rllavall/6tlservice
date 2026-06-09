@echo off
REM Lanza el digest diario de 6TL Postventa (avisos preventivos + SLA) por Telegram/email.
REM Registrado en el Programador de tareas de Windows. Trabaja en su propio
REM directorio (backend\) para que `import app` y la carga de .env funcionen.
cd /d "%~dp0"
".venv\Scripts\python.exe" run_digest.py >> digest.log 2>&1
