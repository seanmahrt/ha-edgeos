from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME

from custom_components.edgeos.common.consts import (
    TRAFFIC_DATA_DIRECTION_RECEIVED,
    TRAFFIC_DATA_DIRECTION_SENT,
    TRAFFIC_DATA_DROPPED,
    TRAFFIC_DATA_ERRORS,
    TRAFFIC_DATA_PACKETS,
    TRAFFIC_STATS_BPS_KEY,
    TRAFFIC_STATS_BYTES,
    WS_INTERFACES_KEY,
)
from custom_components.edgeos.data_processors.system_processor import SystemProcessor
from custom_components.edgeos.models.config_data import ConfigData
from custom_components.edgeos.models.edge_os_system_data import EdgeOSSystemData


def _build_processor() -> SystemProcessor:
    config = ConfigData()
    config.update(
        {
            CONF_HOST: "router.local",
            CONF_USERNAME: "tester",
            CONF_PASSWORD: "secret",
        }
    )
    return SystemProcessor(config)


def test_to_bps_parses_common_units() -> None:
    assert SystemProcessor._to_bps("1000") == 1000.0
    assert SystemProcessor._to_bps("1kbps") == 1000.0
    assert SystemProcessor._to_bps("2 mbit") == 2_000_000.0
    assert SystemProcessor._to_bps("0.5gbps") == 500_000_000.0
    assert SystemProcessor._to_bps("invalid") == 0.0


def test_extract_smart_queue_entries_finds_nested_items() -> None:
    processor = _build_processor()

    system_section = {
        "interfaces": {
            "ethernet": {
                "eth0": {
                    "smart-queue": {
                        "upload": {"upload": "10mbit", "download": "20mbit"}
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

    entries = processor._extract_smart_queue_entries(system_section)

    assert len(entries) == 2


def test_update_smart_queue_parameters_aggregates_counts_and_limits() -> None:
    processor = _build_processor()
    system_data = EdgeOSSystemData()

    system_section = {
        "interfaces": {
            "ethernet": {
                "eth0": {
                    "smart-queue": {
                        "upload": {"upload": "10mbit", "download": "20mbit"}
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

    processor._update_smart_queue_parameters(system_data, system_section)

    assert system_data.smart_queue_total == 2
    assert system_data.smart_queue_enabled == 1
    assert system_data.smart_queue_interfaces == 2
    assert system_data.smart_queue_upload_limit == 15_000_000.0
    assert system_data.smart_queue_download_limit == 35_000_000.0


def test_update_smart_queue_statistics_aggregates_imq_interfaces_only() -> None:
    processor = _build_processor()
    system_data = EdgeOSSystemData()

    processor._ws_data = {
        WS_INTERFACES_KEY: {
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
    }

    processor._update_smart_queue_statistics(system_data)

    assert system_data.smart_queue_rx_rate == 1000.0
    assert system_data.smart_queue_tx_rate == 2000.0
    assert system_data.smart_queue_rx_traffic == 10_000.0
    assert system_data.smart_queue_tx_traffic == 20_000.0
    assert system_data.smart_queue_rx_dropped == 1.0
    assert system_data.smart_queue_tx_dropped == 2.0
    assert system_data.smart_queue_rx_errors == 3.0
    assert system_data.smart_queue_tx_errors == 4.0
    assert system_data.smart_queue_rx_packets == 5.0
    assert system_data.smart_queue_tx_packets == 6.0
