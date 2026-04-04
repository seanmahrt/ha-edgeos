from abc import ABC
import logging

from homeassistant.components.number import NumberEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import ATTR_STATE, Platform, UnitOfDataRate, UnitOfInformation
from homeassistant.core import HomeAssistant

from .common.base_entity import IntegrationBaseEntity, async_setup_base_entry
from .common.consts import (
    ACTION_ENTITY_SET_NATIVE_VALUE,
    ATTR_ATTRIBUTES,
    DOMAIN,
    ATTR_UNIT_CONVERTOR,
    ATTR_UNIT_INFORMATION,
    UNIT_MAPPING,
)
from .common.entity_descriptions import IntegrationNumberEntityDescription
from .common.enums import DeviceTypes
from .managers.coordinator import Coordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    _LOGGER.info("Setting up EdgeOS number platform for entry %s", entry.entry_id)
    coordinator = hass.data[DOMAIN][entry.entry_id]
    coordinator.set_platform_setup_status("number", "starting")

    try:
        await async_setup_base_entry(
            hass,
            entry,
            Platform.NUMBER,
            IntegrationNumberEntity,
            async_add_entities,
        )
        coordinator.set_platform_setup_status("number", "ok")
    except Exception as ex:
        coordinator.set_platform_setup_status("number", f"error: {ex}")
        _LOGGER.exception("EdgeOS number platform setup failed")
        raise


class IntegrationNumberEntity(IntegrationBaseEntity, NumberEntity, ABC):
    """Representation of a sensor."""

    def __init__(
        self,
        hass: HomeAssistant,
        entity_description: IntegrationNumberEntityDescription,
        coordinator: Coordinator,
        device_type: DeviceTypes,
        item_id: str | None,
    ):
        super().__init__(hass, entity_description, coordinator, device_type, item_id)

        self.entity_description = entity_description

        self._attr_native_min_value = entity_description.native_min_value
        self._attr_native_max_value = entity_description.native_max_value
        self._attr_native_step = 1

        self._format_digits: int | None = None
        self._unit_convertor = lambda v: v
        self._inverse_unit_convertor = lambda v: v

        if self._attr_native_unit_of_measurement == UnitOfDataRate.BYTES_PER_SECOND:
            unit = coordinator.config_manager.unit
            unit_settings = UNIT_MAPPING.get(unit, {})
            unit_information = unit_settings.get(
                ATTR_UNIT_INFORMATION, UnitOfInformation.BYTES
            )

            self._unit_convertor = unit_settings.get(ATTR_UNIT_CONVERTOR, lambda v: v)
            self._format_digits = (
                0 if unit_information == UnitOfInformation.BYTES else 3
            )

            if unit_information == UnitOfInformation.KILOBYTES:
                self._inverse_unit_convertor = lambda v: v * 1024
                self._attr_native_unit_of_measurement = UnitOfDataRate.KILOBYTES_PER_SECOND
            elif unit_information == UnitOfInformation.MEGABYTES:
                self._inverse_unit_convertor = lambda v: v * 1024 * 1024
                self._attr_native_unit_of_measurement = UnitOfDataRate.MEGABYTES_PER_SECOND
            else:
                self._inverse_unit_convertor = lambda v: v
                self._attr_native_unit_of_measurement = UnitOfDataRate.BYTES_PER_SECOND

    async def async_set_native_value(self, value: float) -> None:
        """Change the selected option."""
        native_value = self._inverse_unit_convertor(float(value))

        await self.async_execute_device_action(
            ACTION_ENTITY_SET_NATIVE_VALUE,
            native_value,
        )

    def update_component(self, data):
        """Fetch new state parameters for the sensor."""
        if data is not None:
            state = data.get(ATTR_STATE)
            attributes = data.get(ATTR_ATTRIBUTES)

            if state is not None:
                state = self._unit_convertor(float(state))

                if self._format_digits is not None:
                    state = round(state, self._format_digits)

            self._attr_native_value = state
            self._attr_extra_state_attributes = attributes

        else:
            self._attr_native_value = None
