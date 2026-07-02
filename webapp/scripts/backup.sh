#!/usr/bin/env bash
# Backup DB (pg_dump) + file dự án (projects/) → tar.gz mã hóa GPG, giữ quyền chặt.
# Cron gợi ý (2h sáng hằng ngày):  0 2 * * * /app/webapp/scripts/backup.sh >> /var/log/baogia-backup.log 2>&1
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/backups}"
STAMP="$(date +%Y%m%d-%H%M%S)"
GPG_RECIPIENT="${GPG_RECIPIENT:-}"   # để trống = không mã hóa (KHUYẾN NGHỊ điền)

mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# 1) Dump Postgres (chạy trong compose network: dịch vụ 'db').
DUMP="$BACKUP_DIR/db-$STAMP.sql"
pg_dump "${DATABASE_URL}" > "$DUMP"

# 2) Gộp DB dump + thư mục projects/.
ARCHIVE="$BACKUP_DIR/baogia-$STAMP.tar.gz"
tar -czf "$ARCHIVE" -C / "$DUMP" /app/projects
rm -f "$DUMP"

# 3) Mã hóa nếu có GPG recipient.
if [ -n "$GPG_RECIPIENT" ]; then
  gpg --yes --encrypt --recipient "$GPG_RECIPIENT" "$ARCHIVE"
  rm -f "$ARCHIVE"
  ARCHIVE="$ARCHIVE.gpg"
fi
chmod 600 "$ARCHIVE"

# 4) Dọn backup cũ hơn 30 ngày.
find "$BACKUP_DIR" -name 'baogia-*.tar.gz*' -mtime +30 -delete
echo "Backup xong: $ARCHIVE"
