from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "edgeos"
    / "data_processors"
    / "smart_queue_processor.py"
)

SPEC = spec_from_file_location("smart_queue_processor", MODULE_PATH)
SMART_QUEUE_MODULE = module_from_spec(SPEC)
SPEC.loader.exec_module(SMART_QUEUE_MODULE)

TRAFFIC_DATA_DIRECTION_RECEIVED = SMART_QUEUE_MODULE.TRAFFIC_DATA_DIRECTION_RECEIVED
TRAFFIC_DATA_DIRECTION_SENT = SMART_QUEUE_MODULE.TRAFFIC_DATA_DIRECTION_SENT
TRAFFIC_DATA_DROPPED = SMART_QUEUE_MODULE.TRAFFIC_DATA_DROPPED
TRAFFIC_DATA_ERRORS = SMART_QUEUE_MODULE.TRAFFIC_DATA_ERRORS
TRAFFIC_DATA_PACKETS = SMART_QUEUE_MODULE.TRAFFIC_DATA_PACKETS
TRAFFIC_STATS_BPS_KEY = SMART_QUEUE_MODULE.TRAFFIC_STATS_BPS_KEY
TRAFFIC_STATS_BYTES = SMART_QUEUE_MODULE.TRAFFIC_STATS_BYTES

aggregate_smart_queue_parameters = SMART_QUEUE_MODULE.aggregate_smart_queue_parameters
aggregate_smart_queue_statistics = SMART_QUEUE_MODULE.aggregate_smart_queue_statistics
extract_smart_queue_entries = SMART_QUEUE_MODULE.extract_smart_queue_entries
to_bps = SMART_QUEUE_MODULE.to_bps


def test_to_bps_parses_common_units() -> None:
    assert to_bps("1000") == 125.0
    assert to_bps("1kbps") == 125.0
    assert to_bps("2 mbit") == 250_000.0
    assert to_bps("0.5gbps") == 62_500_000.0
    assert to_bps("invalid") == 0.0


def test_extract_smart_queue_entries_finds_nested_items() -> None:
    system_section = {
        "interfaces": {
            "ethernet": {
                "eth0": {
                    "smart-queue": {
                        "upload": {
                            "upload": "10mbit",
                            "download": "20mbit",
                            "queue-type": "fq_codel",
                        }
                    }
                },
                "eth1": {
                    "smart_queue": {
                        "download": {
                            "upload-rate": "5mbit",
                            "download-rate": "15mbit",
                            "disable": None,
                        }
                    }
                },
            }
        }
    }

    entries = extract_smart_queue_entries(system_section)

    assert len(entries) == 2
    assert entries[0]["interface"] == "eth0"
    assert entries[0]["name"] == "upload"


def test_aggregate_smart_queue_parameters_includes_advanced_settings() -> None:
    system_section = {
        "interfaces": {
            "ethernet": {
                "eth0": {
                    "smart-queue": {
                        "upload": {
                            "upload": "10mbit",
                            "download": "20mbit",
                            "queue-type": "fq_codel",
                            "fq-codel": {
                                "target": "5ms",
                                "interval": "100ms",
                            },
                        }
                    }
                },
                "eth1": {
                    "smart_queue": {
                        "download": {
                            "upload-rate": "5mbit",
                            "download-rate": "15mbit",
                            "disable": None,
                            "queue-type": "cake",
                        }
                    }
                },
            }
        }
    }

    data = aggregate_smart_queue_parameters(system_section)

    assert data["smart_queue_total"] == 2
    assert data["smart_queue_enabled"] == 1
    assert data["smart_queue_interfaces"] == 2
    assert data["smart_queue_upload_limit"] == 1_875_000.0
    assert data["smart_queue_download_limit"] == 4_375_000.0
    assert data["smart_queue_advanced_settings"]["eth0:upload"]["queue-type"] == "fq_codel"
    assert (
        data["smart_queue_advanced_settings"]["eth0:upload"]["fq-codel"]["target"]
        == "5ms"
    )
    assert data["smart_queue_advanced_settings"]["eth1:download"]["queue-type"] == "cake"
    assert data["smart_queue_upload_enabled"] == 1
    assert data["smart_queue_upload_disabled"] == 1
    assert data["smart_queue_download_enabled"] == 1
    assert data["smart_queue_download_disabled"] == 1


def test_aggregate_smart_queue_parameters_supports_arbitrary_queue_name() -> None:
    system_section = {
        "traffic-control": {
            "smart-queue": {
                "Tmo": {
                    "wan-interface": "eth0",
                    "upload": {
                        "rate": "12mbit",
                        "ecn": "disable",
                        "flows": "1024",
                        "target": "50ms",
                    },
                }
            }
        }
    }

    data = aggregate_smart_queue_parameters(system_section)

    assert data["smart_queue_total"] == 1
    assert data["smart_queue_enabled"] == 1
    assert data["smart_queue_interfaces"] == 1
    assert data["smart_queue_upload_limit"] == 1_500_000.0
    assert data["smart_queue_download_limit"] == 0.0
    assert data["smart_queue_advanced_settings"]["eth0:Tmo"]["upload"]["flows"] == "1024"
    assert data["smart_queue_upload_enabled"] == 1
    assert data["smart_queue_upload_disabled"] == 0


def test_aggregate_smart_queue_statistics_aggregates_imq_interfaces_only() -> None:
    interfaces_data = {
        "imq0": {
            f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_STATS_BPS_KEY}": 1000,
            f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_STATS_BPS_KEY}": 2000,
            f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_STATS_BYTES}": 10_000,
            f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_STATS_BYTES}": 20_000,
            f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_DATA_DROPPED}": 1,
            f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_DATA_DROPPED}": 2,
            f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_DATA_ERRORS}": 3,
            f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_DATA_ERRORS}": 4,
            f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_DATA_PACKETS}": 5,
            f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_DATA_PACKETS}": 6,
        },
        "eth0": {
            f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_STATS_BPS_KEY}": 999999,
            f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_STATS_BPS_KEY}": 999999,
        },
    }

    totals = aggregate_smart_queue_statistics(interfaces_data)

    assert totals["smart_queue_rx_rate"] == 1000.0
    assert totals["smart_queue_tx_rate"] == 2000.0
    assert totals["smart_queue_rx_traffic"] == 10_000.0
    assert totals["smart_queue_tx_traffic"] == 20_000.0
    assert totals["smart_queue_rx_dropped"] == 1.0
    assert totals["smart_queue_tx_dropped"] == 2.0
    assert totals["smart_queue_rx_errors"] == 3.0
    assert totals["smart_queue_tx_errors"] == 4.0
    assert totals["smart_queue_rx_packets"] == 5.0
    assert totals["smart_queue_tx_packets"] == 6.0
