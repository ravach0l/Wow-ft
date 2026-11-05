#!/bin/sh
# Konsistente Kopie der SQLite-Datenbank, z. B. täglich per cron:
#   15 4 * * * /pfad/zu/wow-ft/deploy/backup.sh
set -eu
cd "$(dirname "$0")"
mkdir -p backups
stamp=$(date +%Y%m%d)
docker compose exec -T wowft python -c "
import sqlite3
src = sqlite3.connect('/data/wowft.db')
dst = sqlite3.connect('/data/backup.db')
src.backup(dst)
dst.close()
"
mv data/backup.db "backups/wowft-$stamp.db"
# 30 Tage aufheben
find backups -name 'wowft-*.db' -mtime +30 -delete
