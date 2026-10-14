#!/bin/bash
# Double-click to set up the Calcium analysis app on this Mac (one time).
cd "$(dirname "$0")" || exit 1
bash scripts/setup_mac.sh
status=$?
echo
if [ $status -eq 0 ]; then
    echo "All done. You can close this window."
else
    echo "Setup did not finish. Read the messages above."
fi
read -n 1 -s -r -p "Press any key to close..."
echo
