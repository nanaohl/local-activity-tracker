#!/bin/bash
SCRIPT_DIR=$(dirname "$0")
source "$SCRIPT_DIR/venv/bin/activate"
"$SCRIPT_DIR/venv/bin/activity" track "$@"