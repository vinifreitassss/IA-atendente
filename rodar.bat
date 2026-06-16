@echo off
cd /d "%~dp0"

if not exist .venv\Scripts\activate.bat (
  echo Ambiente virtual nao encontrado.
  echo Rode primeiro: python -m venv .venv
  pause
  exit /b 1
)

call .venv\Scripts\activate.bat

if not exist .env (
  echo Arquivo .env nao encontrado. Copiando .env.example para .env...
  copy .env.example .env
)

echo Iniciando IA Atendente em http://localhost:6060
uvicorn app.main:app --host 0.0.0.0 --port 6060 --reload
pause
