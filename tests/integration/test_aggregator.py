from datetime import datetime, timedelta, timezone

from mikroflow.worker.aggregator import aggregate


def _seed(pool):
    hour = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO dhcp_leases (ip, mac, hostname, valid_from) "
            "VALUES (%s,%s,%s,%s)",
            ("192.168.1.10", "AA", "laptop", hour - timedelta(days=1)),
        )
        conn.execute(
            "INSERT INTO ip_domain (ip, domain, status, resolved_at, ttl) "
            "VALUES (%s,%s,%s,%s,%s)",
            ("8.8.8.8", "dns.google", "ok", hour, 86400),
        )
        for i in range(3):  # 3 flows in same hour, same 5-tuple
            conn.execute(
                "INSERT INTO flows_raw (ts, src_ip, dst_ip, src_port, dst_port, "
                "protocol, bytes, packets, exporter_ip) VALUES "
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (hour + timedelta(minutes=i * 10), "192.168.1.10", "8.8.8.8",
                 5000, 443, 6, 100, 2, "10.0.0.1"),
            )
    return hour


def test_aggregate_rolls_up_hour_with_enrichment(pool):
    hour = _seed(pool)
    now = hour + timedelta(hours=2)  # hour 10:00 is complete
    aggregate(pool, now=now)
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT device_name, mac, dst_domain, bytes, packets, flow_count "
            "FROM flows_hourly WHERE hour = %s", (hour,)
        ).fetchone()
    assert row == ("laptop", "AA", "dns.google", 300, 6, 3)


def test_aggregate_collects_mac_when_hostname_missing(pool):
    hour = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO dhcp_leases (ip, mac, hostname, valid_from) "
            "VALUES (%s,%s,%s,%s)",
            ("192.168.1.10", "BC:24:11:DB:51:16", "", hour - timedelta(days=1)),
        )
        conn.execute(
            "INSERT INTO flows_raw (ts, src_ip, dst_ip, src_port, dst_port, "
            "protocol, bytes, packets, exporter_ip) VALUES "
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (hour + timedelta(minutes=5), "192.168.1.10", "8.8.8.8",
             5000, 443, 6, 100, 2, "10.0.0.1"),
        )
    aggregate(pool, now=hour + timedelta(hours=2))
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT device_name, mac FROM flows_hourly WHERE hour = %s", (hour,)
        ).fetchone()
    assert row == (None, "BC:24:11:DB:51:16")


def test_aggregate_falls_back_to_nearest_lease(pool):
    # Lease history starts AFTER the flow hour (bootstrap: DHCP synced later).
    hour = datetime(2026, 7, 1, 10, 0, tzinfo=timezone.utc)
    with pool.connection() as conn:
        conn.execute(
            "INSERT INTO dhcp_leases (ip, mac, hostname, valid_from) "
            "VALUES (%s,%s,%s,%s)",
            ("192.168.1.10", "AA", "laptop", hour + timedelta(minutes=54)),
        )
        conn.execute(
            "INSERT INTO flows_raw (ts, src_ip, dst_ip, src_port, dst_port, "
            "protocol, bytes, packets, exporter_ip) VALUES "
            "(%s,%s,%s,%s,%s,%s,%s,%s,%s)",
            (hour + timedelta(minutes=5), "192.168.1.10", "8.8.8.8",
             5000, 443, 6, 100, 2, "10.0.0.1"),
        )
    aggregate(pool, now=hour + timedelta(hours=2))
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT device_name FROM flows_hourly WHERE hour = %s", (hour,)
        ).fetchone()
    assert row == ("laptop",)


def test_aggregate_is_idempotent(pool):
    hour = _seed(pool)
    now = hour + timedelta(hours=2)
    aggregate(pool, now=now)
    aggregate(pool, now=now)  # second run must not double count
    with pool.connection() as conn:
        row = conn.execute(
            "SELECT bytes, flow_count FROM flows_hourly WHERE hour = %s", (hour,)
        ).fetchone()
    assert row == (300, 3)
