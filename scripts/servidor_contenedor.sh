#!/usr/bin/env bash
set -eu

export PORT="${PORT:-8501}"
api_puerto=18000
if [[ "$PORT" == "$api_puerto" ]]; then
    api_puerto=18001
fi
export CONFORME_API_URL="http://127.0.0.1:$api_puerto"

uvicorn app:app --host 127.0.0.1 --port "$api_puerto" --proxy-headers --forwarded-allow-ips 127.0.0.1 &
api_pid=$!
frontend_pid=

detener() {
    kill -TERM "$api_pid" 2>/dev/null || true
    if [[ -n "$frontend_pid" ]]; then
        kill -TERM "$frontend_pid" 2>/dev/null || true
        wait "$frontend_pid" 2>/dev/null || true
    fi
    wait "$api_pid" 2>/dev/null || true
}
trap detener EXIT
trap 'exit 143' TERM
trap 'exit 130' INT

python - <<'PY'
from os import environ
from time import monotonic, sleep
from urllib.request import urlopen

limite = monotonic() + 25
while monotonic() < limite:
    try:
        with urlopen(environ["CONFORME_API_URL"] + "/api/salud", timeout=1) as respuesta:
            if respuesta.status == 200:
                break
    except OSError:
        sleep(0.15)
else:
    raise SystemExit("FastAPI no respondió al iniciar el contenedor de Conforme.")
PY

node /app/frontend/server.js &
frontend_pid=$!
wait -n "$api_pid" "$frontend_pid"
