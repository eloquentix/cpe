#!/usr/bin/env bash
# Updates DuckDNS with this host's current public IP.
# Configure: cp duckdns.env.example duckdns.env  then fill in your values.
# Schedule via cron, e.g.:  */5 * * * * /path/to/cpe/duckdns.sh
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=/dev/null
source "$DIR/duckdns.env"

curl -ks "https://www.duckdns.org/update?domains=${DUCKDNS_DOMAIN}&token=${DUCKDNS_TOKEN}&ip=" -o "$DIR/duckdns.log"
echo " $(date)" >> "$DIR/duckdns.log"
