"""Test Hotel-AX __init__."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant

from custom_components.hotel_ax import (
    async_reload_entry,
    async_setup_entry,
    async_unload_entry,
)
from custom_components.hotel_ax.const import DOMAIN
from tests.conftest import MockConfigEntry


async def test_async_setup_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test setting up the integration."""
    mock_config_entry.add_to_hass(hass)

    assert await async_setup_entry(hass, mock_config_entry)
    # runtime_data is set by async_setup_entry directly
    assert hasattr(mock_config_entry, "runtime_data")
    assert mock_config_entry.runtime_data is not None
    # Note: ConfigEntryState.LOADED is only set by the HA config entry manager
    # when it drives setup via async_setup — not when calling async_setup_entry directly.


async def test_async_setup_entry_creates_coordinator(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that setup creates and starts coordinator."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.hotel_ax.HotelAXCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_start = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        assert await async_setup_entry(hass, mock_config_entry)

        # Verify coordinator was created and started
        mock_coordinator_class.assert_called_once_with(hass, mock_config_entry)
        mock_coordinator.async_start.assert_called_once()


async def test_async_setup_entry_registers_update_listener(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that setup registers update listener."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.hotel_ax.HotelAXCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_start = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        assert await async_setup_entry(hass, mock_config_entry)

        # The update listener should be registered
        # We can verify this by checking that add_update_listener was called
        assert len(mock_config_entry.update_listeners) > 0


async def test_async_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test unloading the integration."""
    mock_config_entry.add_to_hass(hass)

    # Setup first
    assert await async_setup_entry(hass, mock_config_entry)

    # Now unload
    assert await async_unload_entry(hass, mock_config_entry)


async def test_async_unload_entry_stops_coordinator(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that unload stops the coordinator."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "custom_components.hotel_ax.HotelAXCoordinator"
    ) as mock_coordinator_class:
        mock_coordinator = MagicMock()
        mock_coordinator.async_start = AsyncMock()
        mock_coordinator.async_stop = AsyncMock()
        mock_coordinator_class.return_value = mock_coordinator

        # Setup
        assert await async_setup_entry(hass, mock_config_entry)

        # Unload
        assert await async_unload_entry(hass, mock_config_entry)

        # Verify coordinator.async_stop was called
        mock_coordinator.async_stop.assert_called_once()


async def test_async_reload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test reloading the integration."""
    mock_config_entry.add_to_hass(hass)

    # Setup first
    assert await async_setup_entry(hass, mock_config_entry)

    with patch.object(hass.config_entries, "async_reload") as mock_reload:
        mock_reload.return_value = AsyncMock()

        await async_reload_entry(hass, mock_config_entry)

        mock_reload.assert_called_once_with(mock_config_entry.entry_id)


async def test_full_lifecycle(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test full lifecycle: setup -> unload."""
    mock_config_entry.add_to_hass(hass)

    # Setup
    assert await async_setup_entry(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data
    assert coordinator is not None

    # Unload
    assert await async_unload_entry(hass, mock_config_entry)


async def test_setup_with_invalid_coordinator_config(
    hass: HomeAssistant, mock_otel_providers
):
    """Test setup fails gracefully with invalid coordinator config."""
    from custom_components.hotel_ax.const import (
        CONF_API_TOKEN,
        CONF_REGION,
        CONF_LOGS_DATASET,
        CONF_METRICS_DATASET,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: "token",
            CONF_REGION: "invalid-region",
            CONF_LOGS_DATASET: "logs",
            CONF_METRICS_DATASET: "metrics",
        },
    )
    entry.add_to_hass(hass)

    with pytest.raises(ValueError):
        await async_setup_entry(hass, entry)


async def test_multiple_setup_calls(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that multiple setup calls work correctly."""
    mock_config_entry.add_to_hass(hass)

    # First setup
    assert await async_setup_entry(hass, mock_config_entry)
    first_coordinator = mock_config_entry.runtime_data

    # Unload
    assert await async_unload_entry(hass, mock_config_entry)

    # Setup again
    assert await async_setup_entry(hass, mock_config_entry)
    second_coordinator = mock_config_entry.runtime_data

    # Should be different coordinator instances
    assert first_coordinator is not second_coordinator

    # Cleanup
    await async_unload_entry(hass, mock_config_entry)


async def test_unload_without_setup(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that unload without setup handles gracefully."""
    mock_config_entry.add_to_hass(hass)

    # Create a mock coordinator and attach it directly
    mock_coordinator = MagicMock()
    mock_coordinator.async_stop = AsyncMock()
    mock_config_entry.runtime_data = mock_coordinator

    # Should not raise
    assert await async_unload_entry(hass, mock_config_entry)
    mock_coordinator.async_stop.assert_called_once()
