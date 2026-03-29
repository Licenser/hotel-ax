"""Test Hotel-AX options flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.hotel_ax.const import (
    CONF_API_TOKEN,
    CONF_CUSTOM_DOMAIN,
    CONF_EXCLUDE_ENTITIES,
    CONF_FLUSH_INTERVAL,
    CONF_LOGS_DATASET,
    CONF_METRICS_DATASET,
    CONF_REGION,
    DEFAULT_FLUSH_INTERVAL,
    DOMAIN,
)
from tests.conftest import MockConfigEntry


async def test_options_flow_form(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, enable_custom_integrations
):
    """Test options flow displays form with current values."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    schema_keys = [key.schema for key in result["data_schema"].schema.keys()]
    assert CONF_API_TOKEN in schema_keys
    assert CONF_REGION in schema_keys
    assert CONF_LOGS_DATASET in schema_keys
    assert CONF_METRICS_DATASET in schema_keys
    assert CONF_FLUSH_INTERVAL in schema_keys


async def test_options_flow_update_flush_interval(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, enable_custom_integrations
):
    """Test updating flush interval."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "test-token-123",
            CONF_REGION: "us-east-1",
            CONF_LOGS_DATASET: "homeassistant-logs",
            CONF_METRICS_DATASET: "homeassistant-metrics",
            CONF_FLUSH_INTERVAL: 60,
            CONF_EXCLUDE_ENTITIES: "",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FLUSH_INTERVAL] == 60


async def test_options_flow_update_exclude_patterns(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, enable_custom_integrations
):
    """Test updating exclude patterns."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "test-token-123",
            CONF_REGION: "us-east-1",
            CONF_LOGS_DATASET: "homeassistant-logs",
            CONF_METRICS_DATASET: "homeassistant-metrics",
            CONF_FLUSH_INTERVAL: DEFAULT_FLUSH_INTERVAL,
            CONF_EXCLUDE_ENTITIES: "sensor.exclude_me, binary_sensor.skip_*",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert (
        result["data"][CONF_EXCLUDE_ENTITIES]
        == "sensor.exclude_me, binary_sensor.skip_*"
    )


async def test_options_flow_custom_domain_required_when_custom_region(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, enable_custom_integrations
):
    """Test that custom domain is required when region is custom."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "test-token-123",
            CONF_REGION: "custom",
            CONF_CUSTOM_DOMAIN: "",
            CONF_LOGS_DATASET: "homeassistant-logs",
            CONF_METRICS_DATASET: "homeassistant-metrics",
            CONF_FLUSH_INTERVAL: DEFAULT_FLUSH_INTERVAL,
            CONF_EXCLUDE_ENTITIES: "",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    assert result["errors"][CONF_CUSTOM_DOMAIN] == "custom_domain_required"


async def test_options_flow_custom_domain_provided_with_custom_region(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, enable_custom_integrations
):
    """Test that custom domain works when provided with custom region."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "test-token-123",
            CONF_REGION: "custom",
            CONF_CUSTOM_DOMAIN: "my-custom.axiom.co",
            CONF_LOGS_DATASET: "homeassistant-logs",
            CONF_METRICS_DATASET: "homeassistant-metrics",
            CONF_FLUSH_INTERVAL: DEFAULT_FLUSH_INTERVAL,
            CONF_EXCLUDE_ENTITIES: "",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_REGION] == "custom"
    assert result["data"][CONF_CUSTOM_DOMAIN] == "my-custom.axiom.co"


async def test_options_flow_whitespace_stripped_from_custom_domain(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, enable_custom_integrations
):
    """Test that whitespace custom domain is accepted."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "test-token-123",
            CONF_REGION: "custom",
            CONF_CUSTOM_DOMAIN: "  whitespace-domain.axiom.co  ",
            CONF_LOGS_DATASET: "homeassistant-logs",
            CONF_METRICS_DATASET: "homeassistant-metrics",
            CONF_FLUSH_INTERVAL: DEFAULT_FLUSH_INTERVAL,
            CONF_EXCLUDE_ENTITIES: "",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_flow_preserves_existing_config(
    hass: HomeAssistant,
    mock_custom_domain_entry: MockConfigEntry,
    enable_custom_integrations,
):
    """Test that options flow preserves existing configuration values."""
    mock_custom_domain_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(
        mock_custom_domain_entry.entry_id
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "test-token-456",
            CONF_REGION: "custom",
            CONF_CUSTOM_DOMAIN: "custom.axiom.co",
            CONF_LOGS_DATASET: "custom-logs",
            CONF_METRICS_DATASET: "custom-metrics",
            CONF_FLUSH_INTERVAL: 60,
            CONF_EXCLUDE_ENTITIES: "sensor.excluded_*",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_TOKEN] == "test-token-456"
    assert result["data"][CONF_CUSTOM_DOMAIN] == "custom.axiom.co"
    assert result["data"][CONF_FLUSH_INTERVAL] == 60
    assert result["data"][CONF_EXCLUDE_ENTITIES] == "sensor.excluded_*"


async def test_options_flow_change_api_token(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, enable_custom_integrations
):
    """Test changing API token through options."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "new-token-xyz",
            CONF_REGION: "us-east-1",
            CONF_LOGS_DATASET: "homeassistant-logs",
            CONF_METRICS_DATASET: "homeassistant-metrics",
            CONF_FLUSH_INTERVAL: DEFAULT_FLUSH_INTERVAL,
            CONF_EXCLUDE_ENTITIES: "",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_API_TOKEN] == "new-token-xyz"


async def test_options_flow_change_datasets(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, enable_custom_integrations
):
    """Test changing dataset names through options."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "test-token-123",
            CONF_REGION: "us-east-1",
            CONF_LOGS_DATASET: "production-logs",
            CONF_METRICS_DATASET: "production-metrics",
            CONF_FLUSH_INTERVAL: DEFAULT_FLUSH_INTERVAL,
            CONF_EXCLUDE_ENTITIES: "",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_LOGS_DATASET] == "production-logs"
    assert result["data"][CONF_METRICS_DATASET] == "production-metrics"


async def test_options_flow_min_flush_interval(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, enable_custom_integrations
):
    """Test minimum flush interval (10s) is accepted."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "test-token-123",
            CONF_REGION: "us-east-1",
            CONF_LOGS_DATASET: "homeassistant-logs",
            CONF_METRICS_DATASET: "homeassistant-metrics",
            CONF_FLUSH_INTERVAL: 10,
            CONF_EXCLUDE_ENTITIES: "",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FLUSH_INTERVAL] == 10


async def test_options_flow_max_flush_interval(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, enable_custom_integrations
):
    """Test maximum flush interval (300s) is accepted."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_API_TOKEN: "test-token-123",
            CONF_REGION: "us-east-1",
            CONF_LOGS_DATASET: "homeassistant-logs",
            CONF_METRICS_DATASET: "homeassistant-metrics",
            CONF_FLUSH_INTERVAL: 300,
            CONF_EXCLUDE_ENTITIES: "",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_FLUSH_INTERVAL] == 300
