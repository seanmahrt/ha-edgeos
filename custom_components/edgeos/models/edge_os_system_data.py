from __future__ import annotations

from datetime import datetime

from ..common.consts import (
    DHCP_SERVER_LEASES,
    SYSTEM_DATA_DISABLE,
    SYSTEM_DATA_ENABLE,
    SYSTEM_DATA_HOSTNAME,
    SYSTEM_DATA_LOGIN_USER_LEVEL,
    SYSTEM_DATA_NTP,
    SYSTEM_DATA_OFFLOAD_HW_NAT,
    SYSTEM_DATA_TIME_ZONE,
    SYSTEM_DATA_TRAFFIC_ANALYSIS_DPI,
    SYSTEM_DATA_TRAFFIC_ANALYSIS_EXPORT,
    USER_LEVEL_ADMIN,
)


class EdgeOSSystemData:
    hostname: str | None
    timezone: str | None
    ntp_servers: list | None
    hardware_offload: bool | None
    ipsec_offload: bool | None
    deep_packet_inspection: bool | None
    traffic_analysis_export: bool | None
    leased_devices: int
    fw_version: str | None
    sw_version: str | None
    upgrade_available: bool
    upgrade_url: str | None
    upgrade_version: str | None
    product: str | None

    uptime: float | None
    cpu: int | None
    mem: int | None
    last_reset: datetime | None
    user_level: str | None
    smart_queue_total: int
    smart_queue_enabled: int
    smart_queue_interfaces: int
    smart_queue_upload_limit: float
    smart_queue_download_limit: float
    smart_queue_rx_rate: float
    smart_queue_tx_rate: float
    smart_queue_rx_traffic: float
    smart_queue_tx_traffic: float
    smart_queue_rx_dropped: float
    smart_queue_tx_dropped: float
    smart_queue_rx_errors: float
    smart_queue_tx_errors: float
    smart_queue_rx_packets: float
    smart_queue_tx_packets: float

    def __init__(self):
        self.hostname = None
        self.timezone = None
        self.ntp_servers = None
        self.hardware_offload = None
        self.ipsec_offload = None
        self.deep_packet_inspection = None
        self.traffic_analysis_export = None
        self.leased_devices = 0
        self.fw_version = None
        self.sw_version = None
        self.product = None
        self.uptime = None
        self.last_reset = None
        self.cpu = None
        self.mem = None
        self.upgrade_available = False
        self.upgrade_url = None
        self.upgrade_version = None
        self.user_level = None
        self.smart_queue_total = 0
        self.smart_queue_enabled = 0
        self.smart_queue_interfaces = 0
        self.smart_queue_upload_limit = 0
        self.smart_queue_download_limit = 0
        self.smart_queue_rx_rate = 0
        self.smart_queue_tx_rate = 0
        self.smart_queue_rx_traffic = 0
        self.smart_queue_tx_traffic = 0
        self.smart_queue_rx_dropped = 0
        self.smart_queue_tx_dropped = 0
        self.smart_queue_rx_errors = 0
        self.smart_queue_tx_errors = 0
        self.smart_queue_rx_packets = 0
        self.smart_queue_tx_packets = 0

    @property
    def is_admin(self) -> bool:
        is_admin = self.user_level == USER_LEVEL_ADMIN

        return is_admin

    @staticmethod
    def is_enabled(data: dict, key: str) -> bool:
        value = data.get(key, SYSTEM_DATA_DISABLE)
        is_enabled = value == SYSTEM_DATA_ENABLE

        return is_enabled

    def to_dict(self):
        obj = {
            SYSTEM_DATA_HOSTNAME: self.hostname,
            SYSTEM_DATA_TIME_ZONE: self.timezone,
            SYSTEM_DATA_NTP: self.ntp_servers,
            SYSTEM_DATA_OFFLOAD_HW_NAT: self.hardware_offload,
            SYSTEM_DATA_TRAFFIC_ANALYSIS_DPI: self.deep_packet_inspection,
            SYSTEM_DATA_TRAFFIC_ANALYSIS_EXPORT: self.traffic_analysis_export,
            DHCP_SERVER_LEASES: self.leased_devices,
            SYSTEM_DATA_LOGIN_USER_LEVEL: self.user_level,
            "smart_queue_total": self.smart_queue_total,
            "smart_queue_enabled": self.smart_queue_enabled,
            "smart_queue_interfaces": self.smart_queue_interfaces,
            "smart_queue_upload_limit": self.smart_queue_upload_limit,
            "smart_queue_download_limit": self.smart_queue_download_limit,
            "smart_queue_rx_rate": self.smart_queue_rx_rate,
            "smart_queue_tx_rate": self.smart_queue_tx_rate,
            "smart_queue_rx_traffic": self.smart_queue_rx_traffic,
            "smart_queue_tx_traffic": self.smart_queue_tx_traffic,
            "smart_queue_rx_dropped": self.smart_queue_rx_dropped,
            "smart_queue_tx_dropped": self.smart_queue_tx_dropped,
            "smart_queue_rx_errors": self.smart_queue_rx_errors,
            "smart_queue_tx_errors": self.smart_queue_tx_errors,
            "smart_queue_rx_packets": self.smart_queue_rx_packets,
            "smart_queue_tx_packets": self.smart_queue_tx_packets,
        }

        return obj

    def __repr__(self):
        to_string = f"{self.to_dict()}"

        return to_string
