"""Config flow for Hotel-AX integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import AbortFlow, FlowResult

from .const import (
    AXIOM_REGIONS,
    AXIOM_REGION_DEFAULT,
    CONF_API_TOKEN,
    CONF_CUSTOM_DOMAIN,
    CONF_LOGS_DATASET,
    CONF_METRICS_DATASET,
    CONF_REGION,
    CONF_HA_LOGS_ENABLED,
    CONF_HA_LOGS_DATASET,
    CONF_HA_LOGS_LEVEL,
    DEFAULT_LOGS_DATASET,
    DEFAULT_METRICS_DATASET,
    DEFAULT_HA_LOGS_ENABLED,
    DEFAULT_HA_LOGS_DATASET,
    DEFAULT_HA_LOGS_LEVEL,
    HA_LOG_LEVELS,
    DOMAIN,
    OTLP_LOGS_PATH,
)

_LOGGER = logging.getLogger(__name__)


async def validate_axiom_connection(
    hass: HomeAssistant,
    api_token: str,
    domain: str,
    dataset: str,
) -> dict[str, Any]:
    """Validate the Axiom connection by attempting a test request."""
    import aiohttp

    url = f"https://{domain}{OTLP_LOGS_PATH}"
    headers = {
        "Authorization": f"Bearer {api_token}",
        "X-Axiom-Dataset": dataset,
        "Content-Type": "application/x-protobuf",
    }

    # Try a minimal HEAD request to validate credentials
    try:
        timeout = aiohttp.ClientTimeout(total=10)
        async with aiohttp.ClientSession() as session:
            async with session.head(url, headers=headers, timeout=timeout) as response:
                if response.status in (
                    200,
                    204,
                    405,
                ):  # 405 is OK (HEAD not supported but auth worked)
                    return {"title": f"Hotel-AX ({domain})"}
                elif response.status == 401:
                    raise InvalidAuth
                elif response.status == 404:
                    raise InvalidDataset
                else:
                    _LOGGER.error("Unexpected response: %s", response.status)
                    raise CannotConnect
    except aiohttp.ClientError as err:
        _LOGGER.error("Connection error: %s", err)
        raise CannotConnect from err


class HotelAXConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Hotel-AX."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        self._data: dict[str, Any] = {}

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> config_entries.OptionsFlow:
        """Get the options flow for this handler."""
        from .options_flow import HotelAXOptionsFlow

        return HotelAXOptionsFlow(config_entry)

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step - credentials and region."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Store the input
            self._data.update(user_input)

            # If custom region, go to custom domain step
            if user_input[CONF_REGION] == "custom":
                return await self.async_step_custom_domain()

            # Otherwise, move to datasets step
            return await self.async_step_datasets()

        # Build the region dropdown options
        region_options = {
            "us-east-1": "US East 1 (AWS)",
            "eu-central-1": "EU Central 1 (AWS)",
            "custom": "Custom",
        }

        data_schema = vol.Schema(
            {
                vol.Required(CONF_API_TOKEN): vol.All(
                    str, vol.Strip, vol.Length(min=1)
                ),
                vol.Required(CONF_REGION, default=AXIOM_REGION_DEFAULT): vol.In(
                    region_options
                ),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_custom_domain(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle custom domain input."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)
            return await self.async_step_datasets()

        def validate_domain(domain: str) -> str:
            """Validate domain doesn't include protocol."""
            domain = domain.strip()
            if domain.startswith(("http://", "https://")):
                raise vol.Invalid("Domain should not include http:// or https://")
            if not domain or "/" in domain:
                raise vol.Invalid("Invalid domain format")
            return domain

        data_schema = vol.Schema(
            {
                vol.Required(CONF_CUSTOM_DOMAIN): vol.All(
                    str, vol.Length(min=1), validate_domain
                ),
            }
        )

        return self.async_show_form(
            step_id="custom_domain",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_datasets(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle dataset configuration."""
        errors: dict[str, str] = {}

        if user_input is not None:
            self._data.update(user_input)

            # Determine the domain to use
            region = self._data.get(CONF_REGION)
            if region == "custom":
                domain = self._data.get(CONF_CUSTOM_DOMAIN)
            else:
                domain = AXIOM_REGIONS.get(region)

            if not domain:
                errors["base"] = "invalid_domain"
            else:
                # Validate connection
                try:
                    info = await validate_axiom_connection(
                        self.hass,
                        self._data[CONF_API_TOKEN],
                        domain,
                        self._data[CONF_LOGS_DATASET],
                    )

                    # Check for existing entries
                    await self.async_set_unique_id(f"hotel_ax_{domain}")
                    self._abort_if_unique_id_configured()

                    return self.async_create_entry(
                        title=info["title"],
                        data=self._data,
                    )
                except AbortFlow:
                    raise  # Let AbortFlow propagate — e.g. already_configured
                except InvalidAuth:
                    errors["base"] = "invalid_auth"
                except InvalidDataset:
                    errors[CONF_LOGS_DATASET] = "invalid_dataset"
                except CannotConnect:
                    errors["base"] = "cannot_connect"
                except Exception as err:
                    _LOGGER.exception("Unexpected exception during validation: %s", err)
                    errors["base"] = "unknown"

        data_schema = vol.Schema(
            {
                vol.Required(CONF_LOGS_DATASET, default=DEFAULT_LOGS_DATASET): vol.All(
                    str, vol.Strip, vol.Length(min=1)
                ),
                vol.Required(
                    CONF_METRICS_DATASET, default=DEFAULT_METRICS_DATASET
                ): vol.All(str, vol.Strip, vol.Length(min=1)),
                vol.Required(
                    CONF_HA_LOGS_ENABLED, default=DEFAULT_HA_LOGS_ENABLED
                ): bool,
                vol.Optional(
                    CONF_HA_LOGS_DATASET, default=DEFAULT_HA_LOGS_DATASET
                ): vol.All(str, vol.Strip, vol.Length(min=1)),
                vol.Optional(CONF_HA_LOGS_LEVEL, default=DEFAULT_HA_LOGS_LEVEL): vol.In(
                    HA_LOG_LEVELS
                ),
            }
        )

        return self.async_show_form(
            step_id="datasets",
            data_schema=data_schema,
            errors=errors,
        )


class CannotConnect(Exception):
    """Error to indicate we cannot connect."""


class InvalidAuth(Exception):
    """Error to indicate invalid authentication."""


class InvalidDataset(Exception):
    """Error to indicate invalid dataset."""
