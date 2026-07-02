from mikroflow.worker.arp import normalize_arp


def test_normalize_filters_incomplete_and_macless():
    rows = [
        {"address": "10.59.0.5", "mac-address": "AA:BB:CC:DD:EE:01", "complete": "true"},
        {"address": "10.59.0.6", "mac-address": "AA:BB:CC:DD:EE:02"},  # complete absent -> kept
        {"address": "10.59.0.7"},                                       # no mac -> skip
        {"mac-address": "AA:BB:CC:DD:EE:03"},                           # no ip -> skip
        {"address": "10.59.0.8", "mac-address": "AA:BB:CC:DD:EE:04", "complete": "false"},  # skip
        {"address": "10.59.0.9", "mac-address": "AA:BB:CC:DD:EE:05", "invalid": "true"},    # skip
    ]
    assert normalize_arp(rows) == [
        ("10.59.0.5", "AA:BB:CC:DD:EE:01"),
        ("10.59.0.6", "AA:BB:CC:DD:EE:02"),
    ]
