#!/bin/sh
set -eu

CERT_DIR=/certs
mkdir -p "$CERT_DIR"

if [ ! -s "$CERT_DIR/ca.key" ] || [ ! -s "$CERT_DIR/ca.crt" ]; then
  openssl req -utf8 -x509 -newkey rsa:2048 -sha256 -days 3650 -nodes \
    -keyout "$CERT_DIR/ca.key" \
    -out "$CERT_DIR/ca.crt" \
    -subj "/CN=Каталог фильмов" \
    -addext "basicConstraints=critical,CA:TRUE" \
    -addext "keyUsage=critical,keyCertSign,cRLSign"
  chmod 600 "$CERT_DIR/ca.key" || true
  echo "удостоверяющий центр каталога создан"
fi

SAN="DNS:localhost,IP:127.0.0.1"

append_name() {
  item=$(printf '%s' "$1" | tr -d '[:space:]')
  [ -z "$item" ] && return 0
  if printf '%s' "$item" | grep -Eq '^[0-9]{1,3}(\.[0-9]{1,3}){3}$'; then
    token="IP:${item}"
  else
    case "$item" in
      *[!A-Za-z0-9.-]*) return 0 ;;
    esac
    token="DNS:${item}"
  fi
  case ",${SAN}," in
    *",${token},"*) return 0 ;;
  esac
  SAN="${SAN},${token}"
}

rest="${TLS_HOSTS:-},${TLS_DNS_NAME:-}"
while [ -n "$rest" ]; do
  case "$rest" in
    *,*)
      item=${rest%%,*}
      rest=${rest#*,}
      ;;
    *)
      item=$rest
      rest=
      ;;
  esac
  append_name "$item"
done

if [ -z "${TLS_HOSTS:-}" ]; then
  echo "TLS_HOSTS пуст: укажите в .env адрес компьютера в сети и пересоздайте контейнер web"
fi

old=$(cat "$CERT_DIR/san.txt" 2>/dev/null || true)
need=0
if [ ! -s "$CERT_DIR/server.crt" ] || [ ! -s "$CERT_DIR/server.key" ]; then
  need=1
elif [ "$old" != "$SAN" ]; then
  need=1
elif ! openssl x509 -checkend 2592000 -noout -in "$CERT_DIR/server.crt" >/dev/null 2>&1; then
  need=1
fi

if [ "$need" = 1 ]; then
  cat > "$CERT_DIR/server.ext" <<EOF
basicConstraints=CA:FALSE
keyUsage=digitalSignature,keyEncipherment
extendedKeyUsage=serverAuth
subjectAltName=${SAN}
EOF
  openssl req -utf8 -newkey rsa:2048 -sha256 -nodes \
    -keyout "$CERT_DIR/server.key" \
    -out "$CERT_DIR/server.csr" \
    -subj "/CN=video-catalog"
  openssl x509 -req \
    -in "$CERT_DIR/server.csr" \
    -CA "$CERT_DIR/ca.crt" \
    -CAkey "$CERT_DIR/ca.key" \
    -CAcreateserial \
    -out "$CERT_DIR/server.crt" \
    -days 825 \
    -sha256 \
    -extfile "$CERT_DIR/server.ext"
  chmod 600 "$CERT_DIR/server.key" || true
  rm -f "$CERT_DIR/server.csr" "$CERT_DIR/server.ext"
  printf '%s' "$SAN" > "$CERT_DIR/san.txt"
  echo "сертификат сайта выпущен: ${SAN}"
fi

cat "$CERT_DIR/server.crt" "$CERT_DIR/ca.crt" > "$CERT_DIR/fullchain.crt"
