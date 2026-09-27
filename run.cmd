@echo off
rem Local preview of the linknode.com site (web/public, served the way the Cloudflare
rem Worker serves it) on http://127.0.0.1:8771. Live data comes from the production
rem eagle-monitor API, which allows this origin via CORS. Extra args go to wrangler dev.
setlocal
set "WRANGLER=%~dp0node_modules\.bin\wrangler.cmd"
if not exist "%WRANGLER%" (
    echo wrangler is not installed. From the repo root run:  npm install
    pause
    exit /b 1
)
"%WRANGLER%" dev --config "%~dp0web\wrangler.jsonc" --ip 127.0.0.1 --port 8771 %*
if errorlevel 1 pause
