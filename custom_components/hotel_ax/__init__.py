"""The Hotel-AX integration."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import HotelAXCoordinator

if TYPE_CHECKING:
    type HotelAXConfigEntry = ConfigEntry[HotelAXCoordinator]

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: HotelAXConfigEntry) -> bool:
    """Set up Hotel-AX from a config entry."""
    _LOGGER.info("Setting up Hotel-AX integration")

    # Create and store the coordinator
    coordinator = HotelAXCoordinator(hass, entry)
    entry.runtime_data = coordinator

    # Start listening to state changes and flushing
    await coordinator.async_start()

    # Register update listener for options changes
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    _LOGGER.info("Hotel-AX integration setup complete")
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    _LOGGER.info("Unloading Hotel-AX integration")

    coordinator: HotelAXCoordinator = entry.runtime_data
    await coordinator.async_stop()

    return True


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)
