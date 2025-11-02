#!/usr/bin/env bash
set -e
# pyenv install 3.12.5
# pyenv local 3.12.5
# Move to script directory
cd "$(dirname "$0")"
export SSL_CERT_FILE=$(python -m certifi)
# Define paths
VENV_DIR="../venv"
APP_DIR="../app"
MAIN_FILE="$APP_DIR/main.py"
REQ_FILE="$APP_DIR/requirements.txt"

# Create venv if missing
if [ ! -d "$VENV_DIR" ]; then
  echo "[INFO] Creating virtual environment at $VENV_DIR ..."
  python3.11 -m venv "$VENV_DIR"
fi

# Activate venv
source "$VENV_DIR/bin/activate"
pip install --upgrade certifi
# pip uninstall aioredis
# Check requirements
if [ -f "$REQ_FILE" ]; then
  echo "[INFO] Checking dependencies..."
  
  pip install -r "$REQ_FILE"
#   MISSING=$(pip install --dry-run -r "$REQ_FILE" 2>&1 | grep "Would install" || true)

#   if [ -n "$MISSING" ]; then
#     echo "[WARNING] Some dependencies are not installed."
#     read -p "Do you want to install requirements from $REQ_FILE? (y/n): " yn
#     case $yn in
#       [Yy]*) pip install -r "$REQ_FILE" ;;
#       [Nn]*) echo "[INFO] Skipping install." ;;
#       *) echo "Please answer y or n."; exit 1 ;;
#     esac
#   fi
else
  echo "[INFO] No requirements.txt found at $REQ_FILE"
fi

# Run FastAPI app
echo "[INFO] Starting FastAPI app..."
export PYTHONPATH="$(cd .. && pwd)/app:$PYTHONPATH"
# pybabel extract -F babel.cfg -o messages.pot .
# pybabel init -i messages.pot -d locales -l fr
# pybabel compile -d locales

exec uvicorn main:app --host 0.0.0.0 --proxy-headers --port 8000 --reload --reload-dir=/Users/elijahmwangi/StudioProjects/python/nexidra/fileq/app

