#!/usr/bin/env bash
set -euo pipefail
# Read-only environment overview. No discovery, local IP addresses or modification.
printf '\nLINUXOPS / READ ONLY SYSTEM PREFLIGHT\n'
printf '%s\n' '======================================'
uname -srm
uptime
printf '\nFILESYSTEM SUMMARY\n'
df -h / 
printf '\nMEMORY SUMMARY\n'
if command -v free >/dev/null; then free -h; else cat /proc/meminfo | head -n 6; fi
printf '\nChecks completed. No system configuration was changed.\n'
