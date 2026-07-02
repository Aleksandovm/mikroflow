from datetime import datetime, timedelta, timezone

_AGG_SQL = """
INSERT INTO flows_hourly
    (hour, src_ip, device_name, mac, dst_ip, dst_domain, dst_port, protocol,
     bytes, packets, flow_count)
SELECT
    date_trunc('hour', f.ts) AS hour,
    f.src_ip,
    l.hostname,
    l.mac,
    f.dst_ip,
    d.domain,
    f.dst_port,
    f.protocol,
    sum(f.bytes),
    sum(f.packets),
    count(*)
FROM flows_raw f
LEFT JOIN LATERAL (
    -- keep hostname and MAC separately; empty hostname becomes NULL
    SELECT nullif(l.hostname, '') AS hostname, l.mac AS mac
    FROM dhcp_leases l
    WHERE l.ip = f.src_ip
    ORDER BY
        -- prefer the lease that actually covered this hour...
        (l.valid_from <= %(hour)s
         AND (l.valid_to IS NULL OR l.valid_to > %(hour)s)) DESC,
        -- ...otherwise fall back to the lease nearest in time (handles the
        -- bootstrap window where lease history starts after the flow hour)
        abs(extract(epoch FROM (l.valid_from - %(hour)s)))
    LIMIT 1
) l ON true
LEFT JOIN ip_domain d ON d.ip = f.dst_ip
WHERE f.ts >= %(hour)s AND f.ts < %(hour)s + interval '1 hour'
GROUP BY 1, f.src_ip, l.hostname, l.mac, f.dst_ip, d.domain, f.dst_port, f.protocol
ON CONFLICT (hour, src_ip, dst_ip, dst_port, protocol) DO UPDATE
SET device_name = EXCLUDED.device_name,
    mac         = EXCLUDED.mac,
    dst_domain  = EXCLUDED.dst_domain,
    bytes       = EXCLUDED.bytes,
    packets     = EXCLUDED.packets,
    flow_count  = EXCLUDED.flow_count
"""


def aggregate(pool, now=None):
    now = now or datetime.now(timezone.utc)
    boundary = now.replace(minute=0, second=0, microsecond=0)
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT last_hour FROM agg_state WHERE name = 'hourly'"
        ).fetchone()
        last = row[0] if row else None
        if last is None:
            first = conn.execute(
                "SELECT date_trunc('hour', min(ts)) FROM flows_raw"
            ).fetchone()[0]
            if first is None:
                return
            last = first
        hour = last
        while hour < boundary:
            conn.execute(_AGG_SQL, {"hour": hour})
            hour = hour + timedelta(hours=1)
            conn.execute(
                "INSERT INTO agg_state (name, last_hour) VALUES ('hourly', %s) "
                "ON CONFLICT (name) DO UPDATE SET last_hour = EXCLUDED.last_hour",
                (hour,),
            )
