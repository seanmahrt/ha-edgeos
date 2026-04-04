import re

TRAFFIC_DATA_DIRECTION_RECEIVED = "rx"
TRAFFIC_DATA_DIRECTION_SENT = "tx"
TRAFFIC_DATA_DROPPED = "dropped"
TRAFFIC_DATA_ERRORS = "errors"
TRAFFIC_DATA_PACKETS = "packets"
TRAFFIC_STATS_BPS_KEY = "bps"
TRAFFIC_STATS_BYTES = "bytes"

SMART_QUEUE_RATE_KEYS = [
    "upload",
    "upload-rate",
    "upload_rate",
    "upload_speed",
    "upload-speed",
    "egress",
    "egress-rate",
    "bandwidth-upload",
]

SMART_QUEUE_DOWNLOAD_KEYS = [
    "download",
    "download-rate",
    "download_rate",
    "download_speed",
    "download-speed",
    "ingress",
    "ingress-rate",
    "bandwidth-download",
]

SMART_QUEUE_NON_ADVANCED_KEYS = set(
    SMART_QUEUE_RATE_KEYS
    + SMART_QUEUE_DOWNLOAD_KEYS
    + ["disable", "enabled", "description", "name", "wan-interface"]
)


def to_float(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def to_bps(value) -> float:
    if value is None:
        return 0.0

    if isinstance(value, (int, float)):
        return float(value)

    value_str = str(value).strip().lower()
    match = re.match(r"^([0-9]+(?:\.[0-9]+)?)\s*([a-zA-Z]+)?$", value_str)

    if match is None:
        return 0.0

    amount = float(match.group(1))
    unit = match.group(2) or "bps"

    multipliers = {
        "bps": 1,
        "k": 1000,
        "kbps": 1000,
        "kbit": 1000,
        "kbits": 1000,
        "mbps": 1000 * 1000,
        "mbit": 1000 * 1000,
        "m": 1000 * 1000,
        "gbps": 1000 * 1000 * 1000,
        "gbit": 1000 * 1000 * 1000,
        "g": 1000 * 1000 * 1000,
    }

    multiplier = multipliers.get(unit, 1)

    # EdgeOS smart-queue rates are bit-based (e.g. 12mbit).
    # HA data-rate sensors in this integration expect bytes/sec values.
    return (amount * multiplier) / 8.0


def get_first_value(data: dict, keys: list[str]):
    for key in keys:
        if key in data:
            return data.get(key)

    return None


def is_queue_enabled(queue_data: dict) -> bool:
    if "disable" in queue_data:
        return False

    enabled = queue_data.get("enabled")
    if isinstance(enabled, str):
        return enabled.lower() in ["true", "enable", "enabled", "yes", "1"]

    if isinstance(enabled, bool):
        return enabled

    return True


def is_section_enabled(section_data: dict | None) -> bool:
    if not isinstance(section_data, dict):
        return True

    if "disable" in section_data:
        return False

    enabled = section_data.get("enabled")
    if isinstance(enabled, str):
        return enabled.lower() in ["true", "enable", "enabled", "yes", "1"]

    if isinstance(enabled, bool):
        return enabled

    return True


def get_direction_state(queue_data: dict, nested_key: str, keys: list[str]) -> tuple[bool, bool]:
    # Direction can be configured as a nested object (upload/download)
    # or as top-level aliases like upload-rate/download-rate.
    if nested_key in queue_data:
        section = queue_data.get(nested_key)

        if isinstance(section, dict):
            return True, is_section_enabled(section)

        if section is not None:
            return True, True

    for key in keys:
        if key in queue_data:
            return True, is_queue_enabled(queue_data)

    return False, False


def extract_smart_queue_entries(system_section: dict) -> list[dict]:
    queue_entries: list[dict] = []

    def _collect(container: dict | list, interface_name: str | None = None):
        if isinstance(container, list):
            for item in container:
                _collect(item, interface_name)
            return

        if not isinstance(container, dict):
            return

        for key, value in container.items():
            if key in ["smart-queue", "smart_queue"] and isinstance(value, dict):
                for name, queue_data in value.items():
                    if isinstance(queue_data, dict):
                        queue_entries.append(
                            {
                                "interface": interface_name or str(name),
                                "name": str(name),
                                "data": queue_data,
                            }
                        )
                continue

            next_interface = interface_name
            if key in ["ethernet", "switch", "vif", "pppoe", "openvpn"]:
                next_interface = interface_name
            elif isinstance(value, dict):
                next_interface = str(key)

            _collect(value, next_interface)

    _collect(system_section)

    return queue_entries


def extract_advanced_settings(queue_data: dict) -> dict:
    advanced = {
        key: value
        for key, value in queue_data.items()
        if key not in SMART_QUEUE_NON_ADVANCED_KEYS
    }

    upload_settings = queue_data.get("upload")
    if isinstance(upload_settings, dict):
        advanced["upload"] = upload_settings

    download_settings = queue_data.get("download")
    if isinstance(download_settings, dict):
        advanced["download"] = download_settings

    return advanced


def _get_queue_rate(queue_data: dict, keys: list[str], nested_key: str) -> float:
    direct_value = get_first_value(queue_data, keys)

    if direct_value is not None and not isinstance(direct_value, dict):
        return to_bps(direct_value)

    nested_section = queue_data.get(nested_key)
    if isinstance(nested_section, dict):
        nested_rate = get_first_value(nested_section, ["rate", *keys])

        if nested_rate is not None and not isinstance(nested_rate, dict):
            return to_bps(nested_rate)

    return 0.0


def aggregate_smart_queue_parameters(system_section: dict) -> dict:
    queue_items = extract_smart_queue_entries(system_section)

    unique_interfaces = set()
    upload_limit = 0.0
    download_limit = 0.0
    enabled_queues = 0
    upload_enabled_count = 0
    upload_disabled_count = 0
    upload_configured_count = 0
    download_enabled_count = 0
    download_disabled_count = 0
    download_configured_count = 0
    advanced_settings: dict[str, dict] = {}
    direction_states: dict[str, dict[str, bool]] = {}
    policy_map: dict[str, dict[str, str]] = {}

    for queue_item in queue_items:
        queue_data = queue_item.get("data", {})
        interface_name = queue_data.get("wan-interface") or queue_item.get("interface")
        queue_name = queue_item.get("name")

        if interface_name is not None:
            unique_interfaces.add(interface_name)

        if is_queue_enabled(queue_data):
            enabled_queues += 1

        upload_configured, upload_enabled = get_direction_state(
            queue_data, "upload", SMART_QUEUE_RATE_KEYS
        )
        download_configured, download_enabled = get_direction_state(
            queue_data, "download", SMART_QUEUE_DOWNLOAD_KEYS
        )

        if upload_configured:
            upload_configured_count += 1
            if upload_enabled:
                upload_enabled_count += 1
            else:
                upload_disabled_count += 1

        if download_configured:
            download_configured_count += 1
            if download_enabled:
                download_enabled_count += 1
            else:
                download_disabled_count += 1

        upload_limit += _get_queue_rate(queue_data, SMART_QUEUE_RATE_KEYS, "upload")
        download_limit += _get_queue_rate(
            queue_data, SMART_QUEUE_DOWNLOAD_KEYS, "download"
        )

        advanced = extract_advanced_settings(queue_data)
        if len(advanced) > 0:
            settings_key = f"{interface_name}:{queue_name}"
            advanced_settings[settings_key] = advanced

        direction_states[f"{interface_name}:{queue_name}"] = {
            "upload_configured": upload_configured,
            "upload_enabled": upload_enabled,
            "download_configured": download_configured,
            "download_enabled": download_enabled,
        }
        policy_map[f"{interface_name}:{queue_name}"] = {
            "policy_name": str(queue_name),
            "wan_interface": str(interface_name),
        }

    return {
        "smart_queue_total": len(queue_items),
        "smart_queue_enabled": enabled_queues,
        "smart_queue_interfaces": len(unique_interfaces),
        "smart_queue_upload_limit": upload_limit,
        "smart_queue_download_limit": download_limit,
        "smart_queue_advanced_settings": advanced_settings,
        "smart_queue_direction_states": direction_states,
        "smart_queue_policy_map": policy_map,
        "smart_queue_wan_interfaces": sorted(list(unique_interfaces)),
        "smart_queue_upload_configured": upload_configured_count,
        "smart_queue_upload_enabled": upload_enabled_count,
        "smart_queue_upload_disabled": upload_disabled_count,
        "smart_queue_download_configured": download_configured_count,
        "smart_queue_download_enabled": download_enabled_count,
        "smart_queue_download_disabled": download_disabled_count,
    }


def aggregate_smart_queue_statistics(
    interfaces_data: dict, queue_prefix: str = "imq"
) -> dict:
    totals = {
        "smart_queue_rx_rate": 0.0,
        "smart_queue_tx_rate": 0.0,
        "smart_queue_rx_traffic": 0.0,
        "smart_queue_tx_traffic": 0.0,
        "smart_queue_rx_dropped": 0.0,
        "smart_queue_tx_dropped": 0.0,
        "smart_queue_rx_errors": 0.0,
        "smart_queue_tx_errors": 0.0,
        "smart_queue_rx_packets": 0.0,
        "smart_queue_tx_packets": 0.0,
    }

    for interface_name in interfaces_data:
        if not interface_name.startswith(queue_prefix):
            continue

        interface_data = interfaces_data.get(interface_name, {})

        totals["smart_queue_rx_rate"] += to_float(
            interface_data.get(
                f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_STATS_BPS_KEY}", 0
            )
        )
        totals["smart_queue_tx_rate"] += to_float(
            interface_data.get(
                f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_STATS_BPS_KEY}", 0
            )
        )
        totals["smart_queue_rx_traffic"] += to_float(
            interface_data.get(
                f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_STATS_BYTES}", 0
            )
        )
        totals["smart_queue_tx_traffic"] += to_float(
            interface_data.get(
                f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_STATS_BYTES}", 0
            )
        )
        totals["smart_queue_rx_dropped"] += to_float(
            interface_data.get(
                f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_DATA_DROPPED}", 0
            )
        )
        totals["smart_queue_tx_dropped"] += to_float(
            interface_data.get(
                f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_DATA_DROPPED}", 0
            )
        )
        totals["smart_queue_rx_errors"] += to_float(
            interface_data.get(
                f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_DATA_ERRORS}", 0
            )
        )
        totals["smart_queue_tx_errors"] += to_float(
            interface_data.get(
                f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_DATA_ERRORS}", 0
            )
        )
        totals["smart_queue_rx_packets"] += to_float(
            interface_data.get(
                f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_DATA_PACKETS}", 0
            )
        )
        totals["smart_queue_tx_packets"] += to_float(
            interface_data.get(
                f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_DATA_PACKETS}", 0
            )
        )

    return totals