"""Switch platform for BMW."""

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
import logging
from typing import Any

from bimmer_connected.models import MyBMWAPIError
from bimmer_connected.vehicle import MyBMWVehicle

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import BMWBaseEntity
from .const import DOMAIN
from .coordinator import BMWDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass
class BMWRequiredKeysMixin:
    """Mixin for required keys."""

    value_fn: Callable[[MyBMWVehicle], bool]
    remote_service_on: Callable[[MyBMWVehicle], Coroutine[Any, Any, Any]]
    remote_service_off: Callable[[MyBMWVehicle], Coroutine[Any, Any, Any]]


@dataclass
class BMWSwitchEntityDescription(SwitchEntityDescription, BMWRequiredKeysMixin):
    """Describes BMW switch entity."""

    is_available: Callable[[MyBMWVehicle], bool] = lambda _: False
    dynamic_options: Callable[[MyBMWVehicle], list[str]] | None = None


NUMBER_TYPES: list[BMWSwitchEntityDescription] = [
    BMWSwitchEntityDescription(
        key="climate",
        name="Climate",
        is_available=lambda v: v.is_remote_climate_stop_enabled,
        value_fn=lambda v: v.climate.is_climate_on,
        remote_service_on=lambda v: v.remote_services.trigger_remote_air_conditioning(),
        remote_service_off=lambda v: v.remote_services.trigger_remote_air_conditioning_stop(),
        icon="mdi:fan",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the MyBMW switch from config entry."""
    coordinator: BMWDataUpdateCoordinator = hass.data[DOMAIN][config_entry.entry_id]

    entities: list[BMWSwitch] = []

    for vehicle in coordinator.account.vehicles:
        if not coordinator.read_only:
            entities.extend(
                [
                    BMWSwitch(coordinator, vehicle, description)
                    for description in NUMBER_TYPES
                    if description.is_available(vehicle)
                ]
            )
    async_add_entities(entities)


class BMWSwitch(BMWBaseEntity, SwitchEntity):
    """Representation of BMW Switch entity."""

    entity_description: BMWSwitchEntityDescription

    def __init__(
        self,
        coordinator: BMWDataUpdateCoordinator,
        vehicle: MyBMWVehicle,
        description: BMWSwitchEntityDescription,
    ) -> None:
        """Initialize an BMW Switch."""
        super().__init__(coordinator, vehicle)
        self.entity_description = description
        self._attr_unique_id = f"{vehicle.vin}-{description.key}"

    @property
    def is_on(self) -> bool:
        """Return the entity value to represent the entity state."""
        return self.entity_description.value_fn(self.vehicle)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the switch on."""
        try:
            await self.entity_description.remote_service_on(self.vehicle)
        except MyBMWAPIError as ex:
            raise HomeAssistantError(ex) from ex

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the switch off."""
        try:
            await self.entity_description.remote_service_off(self.vehicle)
        except MyBMWAPIError as ex:
            raise HomeAssistantError(ex) from ex
