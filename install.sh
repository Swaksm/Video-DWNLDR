#!/usr/bin/env sh
python3 -m pip install -r requirements.txt && python3 -m playwright install chromium
echo "Installation terminee. Lance: ./run.sh"
