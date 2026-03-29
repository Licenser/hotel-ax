"""Test Hotel-AX config flow."""

from __future__ import annotations

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.hotel_ax.config_flow import (
    CannotConnect,
    InvalidAuth,
    InvalidDataset,
    validate_axiom_connection,
)
from custom_components.hotel_ax.const import (
    CONF_API_TOKEN,
    CONF_CUSTOM_DOMAIN,
    CONF_LOGS_DATASET,
    CONF_METRICS_DATASET,
    CONF_REGION,
    DEFAULT_LOGS_DATASET,
    DEFAULT_METRICS_DATASET,
    DOMAIN,
)


def _make_aiohttp_mock(status: int):
    """Build a properly structured aiohttp ClientSession mock.

    The code uses:
        async with aiohttp.ClientSession() as session:
            async with session.head(url, ...) as response:

    So both the session and the response must be async context managers,
    and session.head() must return an async context manager directly
    (not a coroutine).
    """
    response = MagicMock()
    response.status = status
    response.__aenter__ = AsyncMock(return_value=response)
    response.__aexit__ = AsyncMock(return_value=False)

    session = MagicMock()
    # head() must return the response CM directly (not a coroutine)
    session.head.return_value = response
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    mock_cls = MagicMock(return_value=session)
    return mock_cls, response, session


def _make_aiohttp_error_mock(exc: Exception):
    """Build an aiohttp mock that raises on head()."""
    session = MagicMock()
    session.head.side_effect = exc
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)

    mock_cls = MagicMock(return_value=session)
    return mock_cls


# ---------------------------------------------------------------------------
# validate_axiom_connection unit tests
# ---------------------------------------------------------------------------


async def test_validate_axiom_connection_success(hass: HomeAssistant):
    """Test successful validation."""
    mock_cls, _, _ = _make_aiohttp_mock(200)
    with patch("aiohttp.ClientSession", mock_cls):
        result = await validate_axiom_connection(
            hass, "test-token", "us-east-1.aws.edge.axiom.co", "test-dataset"
        )
    assert result == {"title": "Hotel-AX (us-east-1.aws.edge.axiom.co)"}


async def test_validate_axiom_connection_405_accepted(hass: HomeAssistant):
    """Test that 405 (Method Not Allowed) is treated as success."""
    mock_cls, _, _ = _make_aiohttp_mock(405)
    with patch("aiohttp.ClientSession", mock_cls):
        result = await validate_axiom_connection(
            hass, "test-token", "custom.axiom.co", "logs"
        )
    assert result == {"title": "Hotel-AX (custom.axiom.co)"}


async def test_validate_axiom_connection_invalid_auth(hass: HomeAssistant):
    """Test invalid authentication raises InvalidAuth."""
    mock_cls, _, _ = _make_aiohttp_mock(401)
    with patch("aiohttp.ClientSession", mock_cls):
        with pytest.raises(InvalidAuth):
            await validate_axiom_connection(hass, "bad-token", "axiom.co", "logs")


async def test_validate_axiom_connection_invalid_dataset(hass: HomeAssistant):
    """Test 404 raises InvalidDataset."""
    mock_cls, _, _ = _make_aiohttp_mock(404)
    with patch("aiohttp.ClientSession", mock_cls):
        with pytest.raises(InvalidDataset):
            await validate_axiom_connection(hass, "token", "axiom.co", "missing")


async def test_validate_axiom_connection_cannot_connect(hass: HomeAssistant):
    """Test network error raises CannotConnect."""
    mock_cls = _make_aiohttp_error_mock(aiohttp.ClientError("Network error"))
    with patch("aiohttp.ClientSession", mock_cls):
        with pytest.raises(CannotConnect):
            await validate_axiom_connection(hass, "token", "axiom.co", "logs")


async def test_validate_axiom_connection_unexpected_status(hass: HomeAssistant):
    """Test unexpected HTTP status code raises CannotConnect."""
    mock_cls, _, _ = _make_aiohttp_mock(500)
    with patch("aiohttp.ClientSession", mock_cls):
        with pytest.raises(CannotConnect):
            await validate_axiom_connection(hass, "token", "axiom.co", "logs")


# ---------------------------------------------------------------------------
# Config flow UI tests (require enable_custom_integrations)
# ---------------------------------------------------------------------------


async def test_user_step_form(hass: HomeAssistant, enable_custom_integrations):
    """Test the initial user step shows the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert CONF_API_TOKEN in result["data_schema"].schema
    assert CONF_REGION in result["data_schema"].schema


async def test_user_step_standard_region(
    hass: HomeAssistant, enable_custom_integrations
):
    """Test user step with standard region goes to datasets step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "test-token", CONF_REGION: "us-east-1"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "datasets"


async def test_user_step_custom_region(hass: HomeAssistant, enable_custom_integrations):
    """Test user step with custom region goes to custom_domain step."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "test-token", CONF_REGION: "custom"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "custom_domain"


async def test_custom_domain_step(hass: HomeAssistant, enable_custom_integrations):
    """Test custom domain step advances to datasets."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "test-token", CONF_REGION: "custom"},
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_CUSTOM_DOMAIN: "my-custom.axiom.co"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "datasets"


async def test_custom_domain_invalid_with_protocol(
    hass: HomeAssistant, enable_custom_integrations
):
    """Test custom domain rejects http:// prefix.

    Voluptuous schema validation raises InvalidData before the handler runs,
    which is the expected HA behavior for invalid input.
    """
    from homeassistant.data_entry_flow import InvalidData

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "test-token", CONF_REGION: "custom"},
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_CUSTOM_DOMAIN: "http://bad.domain.com"},
        )


async def test_custom_domain_invalid_with_slash(
    hass: HomeAssistant, enable_custom_integrations
):
    """Test custom domain rejects slashes.

    Voluptuous schema validation raises InvalidData before the handler runs.
    """
    from homeassistant.data_entry_flow import InvalidData

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_API_TOKEN: "test-token", CONF_REGION: "custom"},
    )

    with pytest.raises(InvalidData):
        await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_CUSTOM_DOMAIN: "bad.com/path"},
        )


async def test_datasets_step_success(hass: HomeAssistant, enable_custom_integrations):
    """Test successful dataset configuration creates entry."""
    with patch(
        "custom_components.hotel_ax.config_flow.validate_axiom_connection",
        return_value={"title": "Hotel-AX (us-east-1.aws.edge.axiom.co)"},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_TOKEN: "test-token", CONF_REGION: "us-east-1"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOGS_DATASET: "my-logs",
                CONF_METRICS_DATASET: "my-metrics",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Hotel-AX (us-east-1.aws.edge.axiom.co)"
    assert result["data"][CONF_API_TOKEN] == "test-token"
    assert result["data"][CONF_REGION] == "us-east-1"
    assert result["data"][CONF_LOGS_DATASET] == "my-logs"
    assert result["data"][CONF_METRICS_DATASET] == "my-metrics"


async def test_datasets_step_invalid_auth(
    hass: HomeAssistant, enable_custom_integrations
):
    """Test datasets step with invalid auth shows error."""
    with patch(
        "custom_components.hotel_ax.config_flow.validate_axiom_connection",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_TOKEN: "bad-token", CONF_REGION: "us-east-1"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOGS_DATASET: DEFAULT_LOGS_DATASET,
                CONF_METRICS_DATASET: DEFAULT_METRICS_DATASET,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "datasets"
    assert result["errors"]["base"] == "invalid_auth"


async def test_datasets_step_invalid_dataset(
    hass: HomeAssistant, enable_custom_integrations
):
    """Test datasets step with invalid dataset shows error."""
    with patch(
        "custom_components.hotel_ax.config_flow.validate_axiom_connection",
        side_effect=InvalidDataset,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_TOKEN: "test-token", CONF_REGION: "us-east-1"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOGS_DATASET: "nonexistent",
                CONF_METRICS_DATASET: DEFAULT_METRICS_DATASET,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "datasets"
    assert result["errors"][CONF_LOGS_DATASET] == "invalid_dataset"


async def test_datasets_step_cannot_connect(
    hass: HomeAssistant, enable_custom_integrations
):
    """Test datasets step with connection error shows error."""
    with patch(
        "custom_components.hotel_ax.config_flow.validate_axiom_connection",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_TOKEN: "test-token", CONF_REGION: "us-east-1"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOGS_DATASET: DEFAULT_LOGS_DATASET,
                CONF_METRICS_DATASET: DEFAULT_METRICS_DATASET,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "datasets"
    assert result["errors"]["base"] == "cannot_connect"


async def test_datasets_step_unexpected_error(
    hass: HomeAssistant, enable_custom_integrations
):
    """Test datasets step with unexpected error shows error."""
    with patch(
        "custom_components.hotel_ax.config_flow.validate_axiom_connection",
        side_effect=Exception("Unexpected error"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_TOKEN: "test-token", CONF_REGION: "us-east-1"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOGS_DATASET: DEFAULT_LOGS_DATASET,
                CONF_METRICS_DATASET: DEFAULT_METRICS_DATASET,
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "datasets"
    assert result["errors"]["base"] == "unknown"


async def test_duplicate_entry_prevention(
    hass: HomeAssistant, enable_custom_integrations
):
    """Test that duplicate entries are prevented."""
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: "existing-token",
            CONF_REGION: "us-east-1",
            CONF_LOGS_DATASET: "logs",
            CONF_METRICS_DATASET: "metrics",
        },
        unique_id="hotel_ax_us-east-1.aws.edge.axiom.co",
    )
    existing_entry.add_to_hass(hass)

    with patch(
        "custom_components.hotel_ax.config_flow.validate_axiom_connection",
        return_value={"title": "Hotel-AX (us-east-1.aws.edge.axiom.co)"},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_TOKEN: "new-token", CONF_REGION: "us-east-1"},
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_LOGS_DATASET: "logs", CONF_METRICS_DATASET: "metrics"},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_full_custom_domain_flow(hass: HomeAssistant, enable_custom_integrations):
    """Test complete flow with custom domain."""
    with patch(
        "custom_components.hotel_ax.config_flow.validate_axiom_connection",
        return_value={"title": "Hotel-AX (custom.example.com)"},
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_API_TOKEN: "custom-token", CONF_REGION: "custom"},
        )
        assert result["step_id"] == "custom_domain"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_CUSTOM_DOMAIN: "custom.example.com"},
        )
        assert result["step_id"] == "datasets"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOGS_DATASET: "custom-logs",
                CONF_METRICS_DATASET: "custom-metrics",
            },
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_CUSTOM_DOMAIN] == "custom.example.com"
    assert result["data"][CONF_REGION] == "custom"
