#!/usr/bin/env bash
set -e

cd "$(dirname "$0")"

if [ -x ".venv/bin/python" ]; then
    PY_EXE=".venv/bin/python"
elif [ -x "venv/bin/python" ]; then
    PY_EXE="venv/bin/python"
else
    PY_EXE="python3"
fi

if ! "$PY_EXE" -c "import tkinter" >/dev/null 2>&1; then
    echo "[ERREUR] Le module Python 'tkinter' est introuvable."
    echo "Installez-le sous Debian/Ubuntu/Mint avec : sudo apt install python3-tk"
    exit 1
fi

exec "$PY_EXE" gui_anonymizer.py --gui-errors "$@"
