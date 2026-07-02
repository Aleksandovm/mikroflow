from mikroflow.worker.arp import sync_arp


def _arp(pool):
    with pool.connection() as conn:
        return {
            r[0]: r[1]
            for r in conn.execute("SELECT host(ip), mac FROM arp").fetchall()
        }


def test_sync_replaces_snapshot(pool):
    sync_arp(pool, [("10.59.0.5", "AA"), ("10.59.0.6", "BB")])
    assert _arp(pool) == {"10.59.0.5": "AA", "10.59.0.6": "BB"}

    # a later snapshot fully replaces the previous one
    sync_arp(pool, [("10.59.0.6", "CC"), ("10.59.0.7", "DD")])
    assert _arp(pool) == {"10.59.0.6": "CC", "10.59.0.7": "DD"}
