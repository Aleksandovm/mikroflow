from datetime import datetime, timezone

import routeros_api


def fetch_arp(host, user, password, port):
    conn = routeros_api.RouterOsApiPool(
        host, username=user, password=password, port=port, plaintext_login=True
    )
    try:
        api = conn.get_api()
        rows = api.get_resource("/ip/arp").get()
        return [dict(r) for r in rows]
    finally:
        conn.disconnect()


def normalize_arp(rows):
    # -> list of (ip, mac); skip entries without an address or a MAC
    out = []
    for r in rows:
        ip = r.get("address")
        mac = r.get("mac-address")
        if not ip or not mac:
            continue
        if r.get("invalid") == "true" or r.get("complete") == "false":
            continue
        out.append((ip, mac))
    return out


def sync_arp(pool, entries, now=None):
    now = now or datetime.now(timezone.utc)
    with pool.connection() as conn:
        conn.execute("DELETE FROM arp")
        for ip, mac in entries:
            conn.execute(
                "INSERT INTO arp (ip, mac, updated_at) VALUES (%s, %s, %s) "
                "ON CONFLICT (ip) DO UPDATE SET mac = EXCLUDED.mac, "
                "updated_at = EXCLUDED.updated_at",
                (ip, mac, now),
            )
