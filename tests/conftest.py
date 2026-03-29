"""Common test fixtures for Hotel-AX integration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

# Re-export enable_custom_integrations so tests that need it can use it.
# This fixture tells pytest-homeassistant-custom-component to load custom
# integrations from the local custom_components/ directory.
pytest_plugins = "pytest_homeassistant_custom_component"

from custom_components.hotel_ax.const import (
    CONF_API_TOKEN,
    CONF_CUSTOM_DOMAIN,
    CONF_EXCLUDE_ENTITIES,
    CONF_FLUSH_INTERVAL,
    CONF_LOGS_DATASET,
    CONF_METRICS_DATASET,
    CONF_REGION,
    DEFAULT_FLUSH_INTERVAL,
    DEFAULT_LOGS_DATASET,
    DEFAULT_METRICS_DATASET,
    DOMAIN,
)


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Axiom Export",
        data={
            CONF_API_TOKEN: "test-token-123",
            CONF_REGION: "us-east-1",
            CONF_LOGS_DATASET: DEFAULT_LOGS_DATASET,
            CONF_METRICS_DATASET: DEFAULT_METRICS_DATASET,
        },
        options={
            CONF_FLUSH_INTERVAL: DEFAULT_FLUSH_INTERVAL,
            CONF_EXCLUDE_ENTITIES: "",
        },
        unique_id="hotel_ax_test",
    )


@pytest.fixture
def mock_custom_domain_entry() -> MockConfigEntry:
    """Return a mock config entry with custom domain."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Axiom Export (Custom)",
        data={
            CONF_API_TOKEN: "test-token-456",
            CONF_REGION: "custom",
            CONF_CUSTOM_DOMAIN: "custom.axiom.co",
            CONF_LOGS_DATASET: "custom-logs",
            CONF_METRICS_DATASET: "custom-metrics",
        },
        options={
            CONF_FLUSH_INTERVAL: 60,
            CONF_EXCLUDE_ENTITIES: "sensor.excluded_*",
        },
        unique_id="hotel_ax_custom",
    )


@pytest.fixture
def mock_otel_providers():
    """Mock OpenTelemetry providers."""
    with (
        patch("custom_components.hotel_ax.coordinator.MeterProvider") as meter_mock,
        patch("custom_components.hotel_ax.coordinator.LoggerProvider") as logger_mock,
        patch("custom_components.hotel_ax.coordinator.OTLPMetricExporter"),
        patch("custom_components.hotel_ax.coordinator.OTLPLogExporter"),
        patch("custom_components.hotel_ax.coordinator.PeriodicExportingMetricReader"),
        patch("custom_components.hotel_ax.coordinator.BatchLogRecordProcessor"),
        patch("custom_components.hotel_ax.coordinator.Resource"),
    ):
        # Setup mock meter provider
        meter_provider_instance = MagicMock()
        meter_provider_instance.get_meter.return_value = MagicMock()
        meter_provider_instance.force_flush = MagicMock(return_value=True)
        meter_provider_instance.shutdown = MagicMock(return_value=True)
        meter_mock.return_value = meter_provider_instance

        # Setup mock logger providers — use side_effect so each call returns a
        # distinct instance (state-change provider vs. HA general log provider).
        def _make_logger_provider(*args, **kwargs):
            instance = MagicMock()
            instance.get_logger.return_value = MagicMock()
            instance.force_flush = MagicMock(return_value=True)
            instance.shutdown = MagicMock(return_value=True)
            return instance

        logger_mock.side_effect = _make_logger_provider

        yield {
            "meter_provider": meter_provider_instance,
            "logger_provider": logger_mock,
        }


@pytest.fixture
def mock_aiohttp_session():
    """Mock aiohttp session for validation tests."""
    with patch(
        "custom_components.hotel_ax.config_flow.async_get_clientsession"
    ) as mock:
        session = MagicMock()
        mock.return_value = session

        # Setup HEAD request mock
        response = AsyncMock()
        response.status = 200
        response.__aenter__ = AsyncMock(return_value=response)
        response.__aexit__ = AsyncMock(return_value=None)
        session.head.return_value = response

        yield session
