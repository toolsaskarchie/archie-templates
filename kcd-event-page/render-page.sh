#!/bin/sh
# Renders index.html from the four event variables before nginx starts.
# Values are HTML-escaped so an organizer's text can't inject markup.
set -eu

: "${EVENT_NAME:=KCD Argentina}"
: "${CITY:=Buenos Aires}"
: "${MESSAGE:=¡Gracias Argentina! 🇦🇷❤️}"
: "${NEXT_EVENT:=Nos vemos pronto 🤘}"

escape() {
  printf '%s' "$1" | sed -e 's/&/\&amp;/g' -e 's/</\&lt;/g' -e 's/>/\&gt;/g' \
                         -e 's/"/\&quot;/g' -e "s/'/\&#39;/g"
}

EVENT_NAME=$(escape "$EVENT_NAME")
CITY=$(escape "$CITY")
MESSAGE=$(escape "$MESSAGE")
NEXT_EVENT=$(escape "$NEXT_EVENT")
export EVENT_NAME CITY MESSAGE NEXT_EVENT

TEMPLATE="${TEMPLATE:-/usr/share/nginx/index.html.template}"
OUT="${OUT:-/usr/share/nginx/html/index.html}"
envsubst '${EVENT_NAME} ${CITY} ${MESSAGE} ${NEXT_EVENT}' < "$TEMPLATE" > "$OUT"
