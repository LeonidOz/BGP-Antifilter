#!/bin/sh
set -eu

LISTS_FILE="${LISTS_FILE:-/etc/bird/lists.txt}"
INCLUDE_DOMAINS_FILE="${INCLUDE_DOMAINS_FILE:-/etc/bird/include-domains.txt}"
EXCLUDE_DOMAINS_FILE="${EXCLUDE_DOMAINS_FILE:-/etc/bird/exclude-domains.txt}"
UPDATE_INTERVAL="${UPDATE_INTERVAL:-1800}"
ROUTES="/etc/bird/generated/routes.conf"

mkdir -p /etc/bird/generated
mkdir -p /run/bird
touch "$ROUTES"

update_routes() {
  tmp_in="$(mktemp)"
  tmp_ex="$(mktemp)"
  tmp_add="$(mktemp)"
  tmp_out="$(mktemp)"

  echo "Updating routes from $LISTS_FILE"

  if grep -Ev '^[[:space:]]*($|#)' "$LISTS_FILE" | while read -r url; do
      echo "Fetching $url" >&2
      curl -4 --retry 5 --retry-delay 5 -fsSL "$url"
    done \
    | tr -d '\r' \
    | grep -Eo '([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?' \
    | awk '{ p=$1; if (p !~ /\//) p=p "/32"; print p }' \
    | sort -u > "$tmp_in"; then

    : > "$tmp_ex"
    : > "$tmp_add"

    grep -Ev '^[[:space:]]*($|#)' "$EXCLUDE_DOMAINS_FILE" | while read -r domain; do
      echo "Resolving exclude domain $domain" >&2
      getent ahostsv4 "$domain" | awk '{print $1 "/32"}' >> "$tmp_ex" || true
    done

    grep -Ev '^[[:space:]]*($|#)' "$INCLUDE_DOMAINS_FILE" | while read -r domain; do
      echo "Resolving include domain $domain" >&2
      getent ahostsv4 "$domain" | awk '{print $1 "/32"}' >> "$tmp_add" || true
    done

    sort -u -o "$tmp_ex" "$tmp_ex"
    sort -u -o "$tmp_add" "$tmp_add"

    python3 - "$tmp_in" "$tmp_ex" "$tmp_add" "$tmp_out" <<'PY'
import ipaddress
import sys

include_file, exclude_file, add_file, out_file = sys.argv[1:5]

def read_networks(path):
    nets = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if line:
                nets.append(ipaddress.ip_network(line, strict=False))
    return nets

base = read_networks(include_file)
exclude = read_networks(exclude_file)
extra = read_networks(add_file)

combined = base + extra
kept = []
removed = 0

for net in combined:
    if any(net.overlaps(ex) for ex in exclude):
        removed += 1
        continue
    kept.append(net)

unique = sorted(set(kept), key=lambda n: (int(n.network_address), n.prefixlen))

with open(out_file, "w") as f:
    for net in unique:
        f.write(f"    route {net} blackhole;\n")

print(f"Base routes: {len(base)}")
print(f"Added domain routes: {len(extra)}")
print(f"Excluded overlapping routes: {removed}")
print(f"Final routes: {len(unique)}")
PY

    count="$(wc -l < "$tmp_out")"
    echo "Generated $count routes after include/exclude"

    if [ "$count" -gt 0 ]; then
      mv "$tmp_out" "$ROUTES"
      birdc configure || true
    else
      echo "Route list is empty, keeping old routes"
      rm -f "$tmp_out"
    fi
  else
    echo "Failed to download route list"
  fi

  rm -f "$tmp_in" "$tmp_ex" "$tmp_add" "$tmp_out"
}

bird -f -c /etc/bird/bird.conf &
BIRD_PID="$!"

sleep 2
update_routes

while true; do
  sleep "$UPDATE_INTERVAL"
  update_routes
done &

wait "$BIRD_PID"
