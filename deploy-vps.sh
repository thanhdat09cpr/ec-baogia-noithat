#!/usr/bin/env bash
# Deploy E&C báo giá nội thất lên VPS. Chạy 1 dòng:
#   curl -fsSL https://raw.githubusercontent.com/thanhdat09cpr/ec-baogia-noithat/main/deploy-vps.sh | bash
# Idempotent: chạy lại = cập nhật code + build lại. Giữ .env & dữ liệu cũ.
set -euo pipefail

REPO="https://github.com/thanhdat09cpr/ec-baogia-noithat.git"
DIR="/opt/ec-baogia-noithat"
IP="$(curl -fsS -4 ifconfig.me 2>/dev/null || echo '31.97.220.195')"

echo "== 1/6 deps =="
command -v git >/dev/null || { apt-get update -qq && apt-get install -y -qq git; }
docker compose version >/dev/null 2>&1 || { apt-get update -qq && apt-get install -y -qq docker-compose-plugin; }

echo "== 2/6 code -> $DIR =="
if [ -d "$DIR/.git" ]; then
  git -C "$DIR" fetch origin -q && git -C "$DIR" reset --hard origin/main
elif [ -e "$DIR" ]; then
  rm -rf "$DIR" && git clone -q "$REPO" "$DIR"
else
  git clone -q "$REPO" "$DIR"
fi
cd "$DIR"

echo "== 3/6 danh muc (data/ gitignore) =="
mkdir -p data
if [ ! -f data/danh-muc-noi-that.csv ]; then
  cat > data/danh-muc-noi-that.csv <<'CSV'
nhom_ma,nhom_ten,hang_muc,don_vi
I.1,Đồ rời,Giường,cai
I.1,Đồ rời,Tủ đầu giường,cai
I.1,Đồ rời,Minibar,cai
I.1,Đồ rời,Armchair,cai
I.1,Đồ rời,Đèn rời,cai
I.2,Hoàn thiện tường & đồ liền tường,Vách tivi,m2
I.2,Hoàn thiện tường & đồ liền tường,Vách đầu giường,m2
I.2,Hoàn thiện tường & đồ liền tường,Len chân tường,md
I.2,Hoàn thiện tường & đồ liền tường,Tủ quần áo,cai
I.3,Cửa & vách kính,Cửa WC,cai
I.3,Cửa & vách kính,Vách kính WC,cai
I.4,Nội thất trang trí,Thảm,m2
I.4,Nội thất trang trí,Rèm,m2
I.4,Nội thất trang trí,Giấy dán tường,m2
I.5,Phụ kiện,Bản lề,cai
I.5,Phụ kiện,Ray trượt,bo
I.5,Phụ kiện,Tay nắm,cai
I.5,Phụ kiện,LED + máng nhôm,md
CSV
fi

echo "== 4/6 .env =="
if [ ! -f .env ] || ! grep -q '^SECRET_KEY=' .env; then
  PGPW="$(openssl rand -hex 16)"
  SECRET="$(openssl rand -hex 48)"
  {
    echo "POSTGRES_USER=baogia"
    echo "POSTGRES_PASSWORD=$PGPW"
    echo "POSTGRES_DB=baogia"
    echo "DATABASE_URL=postgresql+psycopg://baogia:$PGPW@db:5432/baogia"
    echo "SECRET_KEY=$SECRET"
    echo "ANTHROPIC_API_KEY="
    echo "TAKEOFF_MODEL=claude-opus-4-8"
    echo "USD_VND_RATE=25000"
  } > .env
  echo ".env moi da tao"
else
  echo ".env da co, giu nguyen"
fi

echo "== 5/6 chon cong (uu tien 80, ban dang dung thi 8000) =="
if ss -tlnp 2>/dev/null | grep -q ':80 '; then PORT=8000; else PORT=80; fi
{
  echo "services:"
  echo "  app:"
  echo "    ports:"
  echo "      - \"$PORT:8000\""
} > docker-compose.override.yml
echo "PORT=$PORT"

echo "== 6/6 build + up (db + migrate + app; bo caddy vi chua co domain) =="
docker compose up -d --build db migrate app

sleep 6
echo "=================== KET QUA ==================="
docker compose ps
echo "-----------------------------------------------"
if curl -fsS "http://127.0.0.1:$PORT/health" >/dev/null 2>&1; then
  echo "HEALTH: OK"
else
  echo "HEALTH: CHUA OK — xem 'docker compose logs app'"
fi
echo "==============================================="
echo "  TRUY CAP:  http://$IP:$PORT"
echo "==============================================="
