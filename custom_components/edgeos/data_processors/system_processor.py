from datetime import datetime
import logging
import re
import sys

from homeassistant.helpers.device_registry import DeviceInfo

from ..common.consts import (
    API_DATA_DHCP_STATS,
    API_DATA_SYS_INFO,
    API_DATA_SYSTEM,
    DATA_SYSTEM_SYSTEM,
    DEFAULT_NAME,
    DHCP_SERVER_LEASED,
    DHCP_SERVER_STATS,
    DISCOVER_DATA_FW_VERSION,
    DISCOVER_DATA_PRODUCT,
    FW_LATEST_STATE_CAN_UPGRADE,
    MANUFACTURER,
    SYSTEM_DATA_HOSTNAME,
    SYSTEM_DATA_LOGIN,
    SYSTEM_DATA_LOGIN_USER,
    SYSTEM_DATA_LOGIN_USER_LEVEL,
    SYSTEM_DATA_NTP,
    SYSTEM_DATA_NTP_SERVER,
    SYSTEM_DATA_OFFLOAD,
    SYSTEM_DATA_OFFLOAD_HW_NAT,
    SYSTEM_DATA_OFFLOAD_IPSEC,
    SYSTEM_DATA_TIME_ZONE,
    SYSTEM_DATA_TRAFFIC_ANALYSIS,
    SYSTEM_DATA_TRAFFIC_ANALYSIS_DPI,
    SYSTEM_DATA_TRAFFIC_ANALYSIS_EXPORT,
    SYSTEM_INFO_DATA_FW_LATEST,
    SYSTEM_INFO_DATA_FW_LATEST_STATE,
    SYSTEM_INFO_DATA_FW_LATEST_URL,
    SYSTEM_INFO_DATA_FW_LATEST_VERSION,
    SYSTEM_INFO_DATA_SW_VER,
    SYSTEM_STATS_DATA_CPU,
    SYSTEM_STATS_DATA_MEM,
    SYSTEM_STATS_DATA_UPTIME,
    TRAFFIC_DATA_DIRECTION_RECEIVED,
    TRAFFIC_DATA_DIRECTION_SENT,
    TRAFFIC_DATA_DROPPED,
    TRAFFIC_DATA_ERRORS,
    TRAFFIC_DATA_PACKETS,
    TRAFFIC_STATS_BPS_KEY,
    TRAFFIC_STATS_BYTES,
    WS_DISCOVER_KEY,
    WS_INTERFACES_KEY,
    WS_SYSTEM_STATS_KEY,
)
from ..common.enums import DeviceTypes, DynamicInterfaceTypes
from ..models.config_data import ConfigData
from ..models.edge_os_system_data import EdgeOSSystemData
from .base_processor import BaseProcessor

_LOGGER = logging.getLogger(__name__)


class SystemProcessor(BaseProcessor):
    _system: EdgeOSSystemData | None = None

    def __init__(self, config_data: ConfigData):
        super().__init__(config_data)

        self.processor_type = DeviceTypes.SYSTEM

        self._system = None

    def get(self) -> EdgeOSSystemData:
        return self._system

    def get_device_info(self, item_id: str | None = None) -> DeviceInfo:
        name = self._system.hostname.upper()

        device_info = DeviceInfo(
            identifiers={(DEFAULT_NAME, name)},
            name=name,
            model=self._system.product,
            manufacturer=MANUFACTURER,
            hw_version=self._system.fw_version,
        )

        return device_info

    def _process_api_data(self):
        super()._process_api_data()

        try:
            system_section = self._api_data.get(API_DATA_SYSTEM, {})
            system_info_section = self._api_data.get(API_DATA_SYS_INFO, {})

            system_details = system_section.get(DATA_SYSTEM_SYSTEM, {})

            system_data = EdgeOSSystemData() if self._system is None else self._system

            system_data.hostname = system_details.get(SYSTEM_DATA_HOSTNAME)
            system_data.timezone = system_details.get(SYSTEM_DATA_TIME_ZONE)

            ntp: dict = system_details.get(SYSTEM_DATA_NTP, {})
            system_data.ntp_servers = ntp.get(SYSTEM_DATA_NTP_SERVER)

            offload: dict = system_details.get(SYSTEM_DATA_OFFLOAD, {})
            hardware_offload = EdgeOSSystemData.is_enabled(
                offload, SYSTEM_DATA_OFFLOAD_HW_NAT
            )
            ipsec_offload = EdgeOSSystemData.is_enabled(
                offload, SYSTEM_DATA_OFFLOAD_IPSEC
            )

            system_data.hardware_offload = hardware_offload
            system_data.ipsec_offload = ipsec_offload

            traffic_analysis: dict = system_details.get(
                SYSTEM_DATA_TRAFFIC_ANALYSIS, {}
            )
            dpi = EdgeOSSystemData.is_enabled(
                traffic_analysis, SYSTEM_DATA_TRAFFIC_ANALYSIS_DPI
            )
            traffic_analysis_export = EdgeOSSystemData.is_enabled(
                traffic_analysis, SYSTEM_DATA_TRAFFIC_ANALYSIS_EXPORT
            )

            system_data.deep_packet_inspection = dpi
            system_data.traffic_analysis_export = traffic_analysis_export

            sw_latest = system_info_section.get(SYSTEM_INFO_DATA_SW_VER)
            fw_latest = system_info_section.get(SYSTEM_INFO_DATA_FW_LATEST, {})

            fw_latest_state = fw_latest.get(SYSTEM_INFO_DATA_FW_LATEST_STATE)
            fw_latest_version = fw_latest.get(SYSTEM_INFO_DATA_FW_LATEST_VERSION)
            fw_latest_url = fw_latest.get(SYSTEM_INFO_DATA_FW_LATEST_URL)

            system_data.upgrade_available = (
                fw_latest_state == FW_LATEST_STATE_CAN_UPGRADE
            )
            system_data.upgrade_url = fw_latest_url
            system_data.upgrade_version = fw_latest_version

            system_data.sw_version = sw_latest

            login_details = system_details.get(SYSTEM_DATA_LOGIN, {})
            users = login_details.get(SYSTEM_DATA_LOGIN_USER, {})
            current_user = users.get(self._config_data.username, {})
            system_data.user_level = current_user.get(SYSTEM_DATA_LOGIN_USER_LEVEL)

            self._update_smart_queue_parameters(system_data, system_section)

            self._system = system_data

            self._update_leased_devices()

            self._validate_admin()
            self._validate_unit_settings()

        except Exception as ex:
            exc_type, exc_obj, tb = sys.exc_info()
            line_number = tb.tb_lineno

            _LOGGER.error(
                f"Failed to extract System data, Error: {ex}, Line: {line_number}"
            )

    def _process_ws_data(self):
        try:
            system_stats_data = self._ws_data.get(WS_SYSTEM_STATS_KEY, {})
            discovery_data = self._ws_data.get(WS_DISCOVER_KEY, {})

            system_data = self._system

            system_data.fw_version = discovery_data.get(DISCOVER_DATA_FW_VERSION)
            system_data.product = discovery_data.get(DISCOVER_DATA_PRODUCT)

            uptime = float(system_stats_data.get(SYSTEM_STATS_DATA_UPTIME, 0))

            system_data.cpu = int(system_stats_data.get(SYSTEM_STATS_DATA_CPU, 0))
            system_data.mem = int(system_stats_data.get(SYSTEM_STATS_DATA_MEM, 0))

            if uptime != system_data.uptime:
                system_data.uptime = uptime
                system_data.last_reset = self._get_last_reset(uptime)

            self._update_smart_queue_statistics(system_data)

        except Exception as ex:
            exc_type, exc_obj, tb = sys.exc_info()
            line_number = tb.tb_lineno

            _LOGGER.error(
                f"Failed to update system statistics, "
                f"Error: {ex}, "
                f"Line: {line_number}"
            )

    def _update_leased_devices(self):
        try:
            unknown_devices = 0
            data_leases_stats_section = self._api_data.get(API_DATA_DHCP_STATS, {})

            subnets = data_leases_stats_section.get(DHCP_SERVER_STATS, {})

            for subnet in subnets:
                subnet_data = subnets.get(subnet, {})
                unknown_devices += int(subnet_data.get(DHCP_SERVER_LEASED, 0))

            self._system.leased_devices = unknown_devices

        except Exception as ex:
            exc_type, exc_obj, tb = sys.exc_info()
            line_number = tb.tb_lineno

            _LOGGER.error(
                f"Failed to extract Unknown Devices data, Error: {ex}, Line: {line_number}"
            )

    def _validate_admin(self):
        try:
            if not self._system.is_admin:
                message = (
                    f"User {self._config_data.username} level is {self._system.user_level}, "
                    f"Interface status switch will not be created as it requires admin role"
                )

                self._unique_log(logging.INFO, message)

        except Exception as ex:
            exc_type, exc_obj, tb = sys.exc_info()
            line_number = tb.tb_lineno

            _LOGGER.error(
                f"Failed to validate if user is admin, Error: {ex}, Line: {line_number}"
            )

    def _validate_unit_settings(self):
        try:
            warning_messages = []

            if not self._system.deep_packet_inspection:
                warning_messages.append("DPI (deep packet inspection) is turned off")

            if not self._system.traffic_analysis_export:
                warning_messages.append("Traffic Analysis Export is turned off")

            if len(warning_messages) > 0:
                warning_message = " and ".join(warning_messages)

                self._unique_log(
                    logging.WARNING,
                    f"Integration will not work correctly since {warning_message}",
                )

        except Exception as ex:
            exc_type, exc_obj, tb = sys.exc_info()
            line_number = tb.tb_lineno

            _LOGGER.error(
                f"Failed to validate unit settings, Error: {ex}, Line: {line_number}"
            )

    @staticmethod
    def _get_last_reset(uptime):
        now = datetime.now().timestamp()
        last_reset = now - uptime

        result = datetime.fromtimestamp(last_reset)

        return result

    def _update_smart_queue_parameters(
        self, system_data: EdgeOSSystemData, system_section: dict
    ):
        queue_items = self._extract_smart_queue_entries(system_section)

        unique_interfaces = set()
        upload_limit = 0.0
        download_limit = 0.0
        enabled_queues = 0

        for queue_item in queue_items:
            queue_data = queue_item.get("data", {})
            interface_name = queue_item.get("interface")

            if interface_name is not None:
                unique_interfaces.add(interface_name)

            if self._is_queue_enabled(queue_data):
                enabled_queues += 1

            upload_limit += self._to_bps(
                self._get_first_value(
                    queue_data,
                    [
                        "upload",
                        "upload-rate",
                        "upload_rate",
                        "upload_speed",
                        "upload-speed",
                        "egress",
                        "egress-rate",
                        "bandwidth-upload",
                    ],
                )
            )
            download_limit += self._to_bps(
                self._get_first_value(
                    queue_data,
                    [
                        "download",
                        "download-rate",
                        "download_rate",
                        "download_speed",
                        "download-speed",
                        "ingress",
                        "ingress-rate",
                        "bandwidth-download",
                    ],
                )
            )

        system_data.smart_queue_total = len(queue_items)
        system_data.smart_queue_enabled = enabled_queues
        system_data.smart_queue_interfaces = len(unique_interfaces)
        system_data.smart_queue_upload_limit = upload_limit
        system_data.smart_queue_download_limit = download_limit

    def _update_smart_queue_statistics(self, system_data: EdgeOSSystemData):
        interfaces_data = self._ws_data.get(WS_INTERFACES_KEY, {})
        queue_prefix = str(DynamicInterfaceTypes.INTERMEDIATE_QUEUEING_DEVICE)

        totals = {
            "rx_rate": 0.0,
            "tx_rate": 0.0,
            "rx_traffic": 0.0,
            "tx_traffic": 0.0,
            "rx_dropped": 0.0,
            "tx_dropped": 0.0,
            "rx_errors": 0.0,
            "tx_errors": 0.0,
            "rx_packets": 0.0,
            "tx_packets": 0.0,
        }

        for interface_name in interfaces_data:
            if not interface_name.startswith(queue_prefix):
                continue

            interface_data = interfaces_data.get(interface_name, {})

            totals["rx_rate"] += self._to_float(
                interface_data.get(
                    f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_STATS_BPS_KEY}", 0
                )
            )
            totals["tx_rate"] += self._to_float(
                interface_data.get(
                    f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_STATS_BPS_KEY}", 0
                )
            )
            totals["rx_traffic"] += self._to_float(
                interface_data.get(
                    f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_STATS_BYTES}", 0
                )
            )
            totals["tx_traffic"] += self._to_float(
                interface_data.get(
                    f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_STATS_BYTES}", 0
                )
            )
            totals["rx_dropped"] += self._to_float(
                interface_data.get(
                    f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_DATA_DROPPED}", 0
                )
            )
            totals["tx_dropped"] += self._to_float(
                interface_data.get(
                    f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_DATA_DROPPED}", 0
                )
            )
            totals["rx_errors"] += self._to_float(
                interface_data.get(
                    f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_DATA_ERRORS}", 0
                )
            )
            totals["tx_errors"] += self._to_float(
                interface_data.get(
                    f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_DATA_ERRORS}", 0
                )
            )
            totals["rx_packets"] += self._to_float(
                interface_data.get(
                    f"{TRAFFIC_DATA_DIRECTION_RECEIVED}_{TRAFFIC_DATA_PACKETS}", 0
                )
            )
            totals["tx_packets"] += self._to_float(
                interface_data.get(
                    f"{TRAFFIC_DATA_DIRECTION_SENT}_{TRAFFIC_DATA_PACKETS}", 0
                )
            )

        system_data.smart_queue_rx_rate = totals["rx_rate"]
        system_data.smart_queue_tx_rate = totals["tx_rate"]
        system_data.smart_queue_rx_traffic = totals["rx_traffic"]
        system_data.smart_queue_tx_traffic = totals["tx_traffic"]
        system_data.smart_queue_rx_dropped = totals["rx_dropped"]
        system_data.smart_queue_tx_dropped = totals["tx_dropped"]
        system_data.smart_queue_rx_errors = totals["rx_errors"]
        system_data.smart_queue_tx_errors = totals["tx_errors"]
        system_data.smart_queue_rx_packets = totals["rx_packets"]
        system_data.smart_queue_tx_packets = totals["tx_packets"]

    def _extract_smart_queue_entries(self, system_section: dict) -> list[dict]:
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
                            entry = {
                                "interface": interface_name or str(name),
                                "data": queue_data,
                            }
                            queue_entries.append(entry)
                    continue

                next_interface = interface_name
                if key in ["ethernet", "switch", "vif", "pppoe", "openvpn"]:
                    next_interface = interface_name
                elif isinstance(value, dict):
                    next_interface = str(key)

                _collect(value, next_interface)

        _collect(system_section)

        return queue_entries

    @staticmethod
    def _to_float(value) -> float:
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _get_first_value(data: dict, keys: list[str]):
        for key in keys:
            if key in data:
                return data.get(key)

        return None

    @staticmethod
    def _is_queue_enabled(queue_data: dict) -> bool:
        if "disable" in queue_data:
            return False

        enabled = queue_data.get("enabled")
        if isinstance(enabled, str):
            return enabled.lower() in ["true", "enable", "enabled", "yes", "1"]

        if isinstance(enabled, bool):
            return enabled

        return True

    @staticmethod
    def _to_bps(value) -> float:
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

        return amount * multiplier
