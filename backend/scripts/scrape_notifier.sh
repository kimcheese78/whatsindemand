#!/bin/bash
# Watches the scrape log and sends a macOS notification when each company finishes.
LOG="/Users/henry_c/WhatsInDemand/backend/logs/weekly_scrape.log"
COMPANY=""

tail -f "$LOG" | while IFS= read -r line; do
    # Capture company name from progress lines like [42/165] Stripe (greenhouse)
    if [[ "$line" =~ ^\[([0-9]+/[0-9]+)\]\ (.+)\ \( ]]; then
        COMPANY="${BASH_REMATCH[1]} ${BASH_REMATCH[2]}"
    fi

    # Fire notification on save confirmation or error
    if [[ "$line" =~ "✅ Saved" ]]; then
        JOBS=$(echo "$line" | grep -o '[0-9]* jobs')
        osascript -e "display notification \"$JOBS\" with title \"✅ $COMPANY\" sound name \"default\""
    elif [[ "$line" =~ "❌" ]] && [[ -n "$COMPANY" ]]; then
        osascript -e "display notification \"Failed\" with title \"❌ $COMPANY\" sound name \"Basso\""
    elif [[ "$line" =~ "WEEKLY SCRAPE COMPLETED" ]]; then
        osascript -e "display notification \"All companies done!\" with title \"🎉 Scrape Complete\" sound name \"Glass\""
    fi
done
