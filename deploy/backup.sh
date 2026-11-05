#!/bin/sh
# Konsistente Kopie der SQLite-Datenbank, z. B. täglich per cron:
#   15 4 * * * /pfad/zu/wow-ft/deploy/backup.sh
# Die Sicherung entsteht im Container (/tmp) und wird über stdout in backups/ geschrieben,
# weil data/ dem Container-Benutzer gehört und der Host-Benutzer dort nichts verschieben darf.
set -eu
cd "$(dirname "$0")"
mkdir -p backups
stamp=$(date +%Y%m%d)
target="backups/wowft-$stamp.db"
docker compose exec -T wowft python -c "
import os, sqlite3, sys
src = sqlite3.connect('/data/wowft.db')
dst = sqlite3.connect('/tmp/backup.db')
src.backup(dst)
dst.close()
sys.stdout.buffer.write(open('/tmp/backup.db', 'rb').read())
os.remove('/tmp/backup.db')
" > "$target.tmp"
mv "$target.tmp" "$target"
# 30 Tage aufheben
find backups -name 'wowft-*.db' -mtime +30 -delete
