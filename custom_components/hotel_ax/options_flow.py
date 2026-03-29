"""Options flow for Hotel-AX integration."""

from __future__ import annotations

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    AXIOM_REGIONS,
    CONF_API_TOKEN,
    CONF_CUSTOM_DOMAIN,
    CONF_EXCLUDE_ENTITIES,
    CONF_FLUSH_INTERVAL,
    CONF_LOGS_DATASET,
    CONF_METRICS_DATASET,
    CONF_REGION,
    CONF_HA_LOGS_ENABLED,
    CONF_HA_LOGS_DATASET,
    CONF_HA_LOGS_LEVEL,
    DEFAULT_FLUSH_INTERVAL,
    DEFAULT_HA_LOGS_ENABLED,
    DEFAULT_HA_LOGS_DATASET,
    DEFAULT_HA_LOGS_LEVEL,
    HA_LOG_LEVELS,
    DOMAIN,
    MAX_FLUSH_INTERVAL,
    MIN_FLUSH_INTERVAL,
)


class HotelAXOptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for Hotel-AX."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        """Initialize options flow."""
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            # Validate custom domain if region is custom
            if user_input.get(CONF_REGION) == "custom":
                custom_domain = user_input.get(CONF_CUSTOM_DOMAIN, "").strip()
                if not custom_domain:
                    errors[CONF_CUSTOM_DOMAIN] = "custom_domain_required"

            if not errors:
                return self.async_create_entry(title="", data=user_input)

        # Get current values
        current_data = {**self._config_entry.data, **self._config_entry.options}

        # Determine current region/domain
        current_region = current_data.get(CONF_REGION, "us-east-1")
        current_custom_domain = current_data.get(CONF_CUSTOM_DOMAIN, "")

        # Build region options
        region_options = {
            "us-east-1": "US East 1 (AWS)",
            "eu-central-1": "EU Central 1 (AWS)",
            "custom": "Custom",
        }

        # Build schema
        schema = vol.Schema(
            {
                vol.Required(
                    CONF_API_TOKEN,
                    default=current_data.get(CONF_API_TOKEN, ""),
                ): vol.All(str, vol.Strip, vol.Length(min=1)),
                vol.Required(
                    CONF_REGION,
                    default=current_region,
                ): vol.In(region_options),
                vol.Optional(
                    CONF_CUSTOM_DOMAIN,
                    default=current_custom_domain,
                ): str,
                vol.Required(
                    CONF_LOGS_DATASET,
                    default=current_data.get(CONF_LOGS_DATASET, "homeassistant-logs"),
                ): vol.All(str, vol.Strip, vol.Length(min=1)),
                vol.Required(
                    CONF_METRICS_DATASET,
                    default=current_data.get(
                        CONF_METRICS_DATASET, "homeassistant-metrics"
                    ),
                ): vol.All(str, vol.Strip, vol.Length(min=1)),
                vol.Required(
                    CONF_FLUSH_INTERVAL,
                    default=current_data.get(
                        CONF_FLUSH_INTERVAL, DEFAULT_FLUSH_INTERVAL
                    ),
                ): vol.All(
                    vol.Coerce(int),
                    vol.Range(min=MIN_FLUSH_INTERVAL, max=MAX_FLUSH_INTERVAL),
                ),
                vol.Optional(
                    CONF_EXCLUDE_ENTITIES,
                    default=current_data.get(CONF_EXCLUDE_ENTITIES, ""),
                ): str,
                vol.Required(
                    CONF_HA_LOGS_ENABLED,
                    default=current_data.get(
                        CONF_HA_LOGS_ENABLED, DEFAULT_HA_LOGS_ENABLED
                    ),
                ): bool,
                vol.Optional(
                    CONF_HA_LOGS_DATASET,
                    default=current_data.get(
                        CONF_HA_LOGS_DATASET, DEFAULT_HA_LOGS_DATASET
                    ),
                ): vol.All(str, vol.Strip, vol.Length(min=1)),
                vol.Optional(
                    CONF_HA_LOGS_LEVEL,
                    default=current_data.get(CONF_HA_LOGS_LEVEL, DEFAULT_HA_LOGS_LEVEL),
                ): vol.In(HA_LOG_LEVELS),
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema, errors=errors)
