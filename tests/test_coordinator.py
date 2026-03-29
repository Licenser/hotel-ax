"""Test Hotel-AX coordinator."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import HomeAssistant, State
from homeassistant.util import dt as dt_util

from custom_components.hotel_ax.coordinator import HotelAXCoordinator, _ha_unit_to_ucum
from custom_components.hotel_ax.const import (
    CONF_EXCLUDE_ENTITIES,
    CONF_FLUSH_INTERVAL,
)
from tests.conftest import MockConfigEntry


# ---------------------------------------------------------------------------
# Initialization tests
# ---------------------------------------------------------------------------


async def test_coordinator_init_standard_region(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test coordinator initialization with standard region."""
    mock_config_entry.add_to_hass(hass)

    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    assert coordinator.axiom_domain == "us-east-1.aws.edge.axiom.co"
    assert coordinator.api_token == "test-token-123"
    assert coordinator.logs_dataset == "homeassistant-logs"
    assert coordinator.metrics_dataset == "homeassistant-metrics"
    assert coordinator.flush_interval == 30
    assert coordinator.exclude_patterns == []


async def test_coordinator_init_custom_domain(
    hass: HomeAssistant, mock_custom_domain_entry: MockConfigEntry, mock_otel_providers
):
    """Test coordinator initialization with custom domain."""
    mock_custom_domain_entry.add_to_hass(hass)

    coordinator = HotelAXCoordinator(hass, mock_custom_domain_entry)

    assert coordinator.axiom_domain == "custom.axiom.co"
    assert coordinator.api_token == "test-token-456"
    assert coordinator.flush_interval == 60
    assert coordinator.exclude_patterns == ["sensor.excluded_*"]


async def test_coordinator_init_invalid_domain_raises(
    hass: HomeAssistant, mock_otel_providers
):
    """Test coordinator raises ValueError for invalid domain."""
    from custom_components.hotel_ax.const import (
        DOMAIN,
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

    with pytest.raises(ValueError, match="No valid Axiom domain configured"):
        HotelAXCoordinator(hass, entry)


# ---------------------------------------------------------------------------
# Lifecycle tests
# ---------------------------------------------------------------------------


async def test_coordinator_start(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test coordinator start subscribes to events."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    await coordinator.async_start()

    assert coordinator._unsub_state_listener is not None
    assert coordinator._unsub_flush_interval is not None
    assert coordinator._unsub_cache_cleanup is not None

    await coordinator.async_stop()


async def test_coordinator_stop(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test coordinator stop cleans up resources."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    await coordinator.async_start()
    await coordinator.async_stop()

    assert coordinator._unsub_state_listener is None
    assert coordinator._unsub_flush_interval is None
    assert coordinator._unsub_cache_cleanup is None


async def test_async_flush_calls_providers(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test async_flush calls force_flush on providers."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    await coordinator.async_flush()

    mock_otel_providers["meter_provider"].force_flush.assert_called_once()
    coordinator.logger_provider.force_flush.assert_called_once()


# ---------------------------------------------------------------------------
# Unit conversion tests (_ha_unit_to_ucum)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ha_unit,expected_ucum",
    [
        # Temperature
        ("°C", "Cel"),
        ("°F", "[degF]"),
        ("K", "K"),
        # Percentage
        ("%", "%"),
        # Power
        ("W", "W"),
        ("kW", "kW"),
        ("MW", "MW"),
        # Energy
        ("kWh", "kW.h"),
        ("Wh", "W.h"),
        ("MWh", "MW.h"),
        # Voltage — non-ASCII μ → ASCII u
        ("μV", "uV"),
        ("mV", "mV"),
        ("V", "V"),
        # Current
        ("A", "A"),
        ("mA", "mA"),
        # Frequency
        ("Hz", "Hz"),
        ("kHz", "kHz"),
        # Pressure
        ("Pa", "Pa"),
        ("hPa", "hPa"),
        ("bar", "bar"),
        ("mbar", "mbar"),
        ("mmHg", "mm[Hg]"),
        # Concentration — non-ASCII μ → ASCII u
        ("μg/m³", "ug/m3"),
        ("mg/m³", "mg/m3"),
        # Sound
        ("dB", "dB"),
        ("dBm", "dB[mW]"),
        # Length
        ("m", "m"),
        ("km", "km"),
        ("mm", "mm"),
        # Mass — non-ASCII μ → ASCII u
        ("μg", "ug"),
        ("mg", "mg"),
        ("kg", "kg"),
        # Volume
        ("L", "L"),
        ("mL", "mL"),
        ("m³", "m3"),
        # Illuminance
        ("lx", "lx"),
        ("lm", "lm"),
        # Data
        ("B", "By"),
        ("kB", "kBy"),
        ("MB", "MBy"),
        # Angle
        ("°", "deg"),
        # Speed
        ("m/s", "m/s"),
        ("km/h", "km/h"),
        # Time
        ("s", "s"),
        ("min", "min"),
        ("h", "h"),
        # Irradiance
        ("W/m²", "W/m2"),
        # Conductivity — non-ASCII μ → ASCII u
        ("μS/cm", "uS/cm"),
        ("mS/cm", "mS/cm"),
        # Dimensionless
        ("ppm", "[ppm]"),
        ("ppb", "[ppb]"),
        ("UV index", "1"),
    ],
)
def test_ha_unit_to_ucum_known_units(ha_unit, expected_ucum):
    """Test that known HA units map to correct UCUM codes."""
    result = _ha_unit_to_ucum(ha_unit)
    assert result == expected_ucum
    # OTEL constraint: must be ASCII, max 63 chars
    assert result.isascii(), f"Result '{result}' for '{ha_unit}' is not ASCII"
    assert len(result) <= 63, f"Result '{result}' for '{ha_unit}' exceeds 63 chars"


def test_ha_unit_to_ucum_empty_string():
    """Test empty unit maps to dimensionless '1'."""
    assert _ha_unit_to_ucum("") == "1"


def test_ha_unit_to_ucum_none_like_empty():
    """Test None-like empty value maps to dimensionless '1'."""
    assert _ha_unit_to_ucum("") == "1"


def test_ha_unit_to_ucum_unknown_ascii_unit():
    """Test unknown ASCII unit is passed through as-is."""
    result = _ha_unit_to_ucum("widgets")
    assert result == "widgets"
    assert result.isascii()


def test_ha_unit_to_ucum_unknown_non_ascii_fallback():
    """Test unknown non-ASCII unit has non-ASCII chars stripped."""
    # Simulate a custom sensor with a non-ASCII unit not in our map
    result = _ha_unit_to_ucum("µΩ/cm")  # not in our map
    assert result.isascii()
    assert len(result) <= 63


def test_ha_unit_to_ucum_result_always_ascii():
    """Test all mapped units produce valid ASCII output."""
    from custom_components.hotel_ax.coordinator import _HA_UNIT_TO_UCUM

    for ha_unit, ucum in _HA_UNIT_TO_UCUM.items():
        assert ucum.isascii(), f"UCUM code '{ucum}' for '{ha_unit}' is not ASCII"
        assert len(ucum) <= 63, f"UCUM code '{ucum}' for '{ha_unit}' exceeds 63 chars"


def test_ha_unit_to_ucum_long_unknown_unit_truncated():
    """Test that an unknown unit longer than 63 chars is truncated."""
    long_unit = "a" * 100
    result = _ha_unit_to_ucum(long_unit)
    assert len(result) <= 63


# ---------------------------------------------------------------------------
# Metric recording tests
# ---------------------------------------------------------------------------


async def test_record_metric_uses_device_class_in_name(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test _record_metric uses ha.sensor.<device_class> as metric name."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.living_room_temp",
        "22.5",
        attributes={
            "friendly_name": "Living Room Temp",
            "unit_of_measurement": "°C",
            "device_class": "temperature",
        },
    )

    coordinator._record_metric(state, 22.5)

    # Cache key is (metric_name, ucum_unit)
    cache_key = ("ha.sensor.temperature", "Cel")
    assert cache_key in coordinator._gauge_cache


async def test_record_metric_falls_back_to_domain_when_no_device_class(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test _record_metric falls back to ha.sensor.<domain> when no device_class."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.custom_thing",
        "42.0",
        attributes={
            "friendly_name": "Custom Thing",
            "unit_of_measurement": "widgets",
            # No device_class
        },
    )

    coordinator._record_metric(state, 42.0)

    cache_key = ("ha.sensor.sensor", "widgets")
    assert cache_key in coordinator._gauge_cache


async def test_record_metric_ucum_unit_used_not_raw_ha_unit(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that the UCUM unit is passed to create_gauge, not the raw HA unit."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.outdoor_temp",
        "72.0",
        attributes={
            "unit_of_measurement": "°F",
            "device_class": "temperature",
        },
    )

    coordinator._record_metric(state, 72.0)

    # The gauge must be cached under the UCUM key [degF], not °F
    cache_key = ("ha.sensor.temperature", "[degF]")
    assert cache_key in coordinator._gauge_cache

    # Verify create_gauge was called with UCUM unit
    coordinator.meter.create_gauge.assert_called_once_with(
        name="ha.sensor.temperature",
        description="Home Assistant temperature sensor",
        unit="[degF]",
    )


async def test_record_metric_shared_gauge_across_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that entities with same device_class+unit share one gauge instrument."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state1 = State(
        "sensor.bedroom_temp",
        "20.0",
        attributes={"unit_of_measurement": "°C", "device_class": "temperature"},
    )
    state2 = State(
        "sensor.kitchen_temp",
        "22.0",
        attributes={"unit_of_measurement": "°C", "device_class": "temperature"},
    )

    coordinator._record_metric(state1, 20.0)
    coordinator._record_metric(state2, 22.0)

    # Only one cache entry — both sensors share the same instrument
    assert len(coordinator._gauge_cache) == 1
    cache_key = ("ha.sensor.temperature", "Cel")
    assert cache_key in coordinator._gauge_cache

    # create_gauge called only once
    coordinator.meter.create_gauge.assert_called_once()

    # But set() called twice — once per entity
    gauge = coordinator._gauge_cache[cache_key]
    assert gauge.set.call_count == 2


async def test_record_metric_different_units_create_separate_gauges(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that same device_class with different units creates separate gauges."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state_c = State(
        "sensor.temp_celsius",
        "22.0",
        attributes={"unit_of_measurement": "°C", "device_class": "temperature"},
    )
    state_f = State(
        "sensor.temp_fahrenheit",
        "72.0",
        attributes={"unit_of_measurement": "°F", "device_class": "temperature"},
    )

    coordinator._record_metric(state_c, 22.0)
    coordinator._record_metric(state_f, 72.0)

    # Two separate cache entries — different units
    assert ("ha.sensor.temperature", "Cel") in coordinator._gauge_cache
    assert ("ha.sensor.temperature", "[degF]") in coordinator._gauge_cache
    assert len(coordinator._gauge_cache) == 2


async def test_record_metric_attributes_include_entity_id(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that set() is called with entity_id in attributes for time series identity."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.power_meter",
        "1500",
        attributes={
            "friendly_name": "Power Meter",
            "unit_of_measurement": "W",
            "device_class": "power",
            "area_id": "kitchen",
        },
    )

    coordinator._record_metric(state, 1500.0)

    cache_key = ("ha.sensor.power", "W")
    gauge = coordinator._gauge_cache[cache_key]
    gauge.set.assert_called_once()

    call_args = gauge.set.call_args
    assert call_args[0][0] == 1500.0
    attrs = call_args[1]["attributes"]
    assert attrs["entity_id"] == "sensor.power_meter"
    assert attrs["domain"] == "sensor"
    assert attrs["device_class"] == "power"
    assert attrs["friendly_name"] == "Power Meter"
    assert attrs["area_id"] == "kitchen"
    assert attrs["unit_of_measurement"] == "W"


async def test_record_metric_non_ascii_unit_does_not_crash(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that sensors with non-ASCII units (e.g. °F) don't raise exceptions."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.stiebel_return_temp",
        "45.2",
        attributes={
            "unit_of_measurement": "°F",
            "device_class": "temperature",
        },
    )

    # Must not raise — this was the original bug
    coordinator._record_metric(state, 45.2)

    cache_key = ("ha.sensor.temperature", "[degF]")
    assert cache_key in coordinator._gauge_cache


async def test_gauge_cache_reuse_for_same_entity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that repeated state changes for the same entity reuse the same gauge."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state1 = State(
        "sensor.temp",
        "20.0",
        attributes={"unit_of_measurement": "°C", "device_class": "temperature"},
    )
    state2 = State(
        "sensor.temp",
        "21.0",
        attributes={"unit_of_measurement": "°C", "device_class": "temperature"},
    )

    coordinator._record_metric(state1, 20.0)
    first_gauge = coordinator._gauge_cache[("ha.sensor.temperature", "Cel")]

    coordinator._record_metric(state2, 21.0)
    second_gauge = coordinator._gauge_cache[("ha.sensor.temperature", "Cel")]

    # Same gauge object reused
    assert first_gauge is second_gauge
    # create_gauge called only once
    coordinator.meter.create_gauge.assert_called_once()


# ---------------------------------------------------------------------------
# state_class routing tests
# ---------------------------------------------------------------------------


async def test_record_metric_measurement_state_class_uses_gauge(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that state_class=measurement routes to a Gauge instrument."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.living_temp",
        "21.0",
        attributes={
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "state_class": "measurement",
        },
    )

    coordinator._record_metric(state, 21.0)

    # Gauge cache must have an entry; observable cache must be empty
    assert ("ha.sensor.temperature", "Cel") in coordinator._gauge_cache
    assert len(coordinator._observable_cache) == 0
    coordinator.meter.create_gauge.assert_called_once()
    coordinator.meter.create_observable_counter.assert_not_called()
    coordinator.meter.create_observable_up_down_counter.assert_not_called()


async def test_record_metric_measurement_angle_uses_gauge(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that state_class=measurement_angle routes to a Gauge (circular sensors)."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.wind_direction",
        "270.0",
        attributes={
            "unit_of_measurement": "°",
            "device_class": "wind_direction",
            "state_class": "measurement_angle",
        },
    )

    coordinator._record_metric(state, 270.0)

    assert len(coordinator._gauge_cache) == 1
    assert len(coordinator._observable_cache) == 0
    coordinator.meter.create_gauge.assert_called_once()


async def test_record_metric_no_state_class_defaults_to_gauge(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that missing state_class falls back to Gauge for backward compatibility."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.custom",
        "99.0",
        attributes={
            "unit_of_measurement": "widgets",
            # No state_class at all
        },
    )

    coordinator._record_metric(state, 99.0)

    assert len(coordinator._gauge_cache) == 1
    assert len(coordinator._observable_cache) == 0
    coordinator.meter.create_gauge.assert_called_once()


async def test_record_metric_total_increasing_uses_observable_counter(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that state_class=total_increasing routes to an ObservableCounter."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.energy_meter",
        "1234.5",
        attributes={
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
    )

    coordinator._record_metric(state, 1234.5)

    # Observable cache must have an entry; gauge cache must be empty
    cache_key = ("ha.sensor.energy.total", "kW.h", "counter")
    assert cache_key in coordinator._observable_cache
    assert len(coordinator._gauge_cache) == 0
    coordinator.meter.create_observable_counter.assert_called_once_with(
        name="ha.sensor.energy.total",
        callbacks=coordinator.meter.create_observable_counter.call_args[1]["callbacks"],
        description="Home Assistant energy cumulative total sensor",
        unit="kW.h",
    )
    coordinator.meter.create_gauge.assert_not_called()
    coordinator.meter.create_observable_up_down_counter.assert_not_called()


async def test_record_metric_total_uses_observable_up_down_counter(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that state_class=total routes to an ObservableUpDownCounter."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.net_energy",
        "500.0",
        attributes={
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total",
        },
    )

    coordinator._record_metric(state, 500.0)

    cache_key = ("ha.sensor.energy.net", "kW.h", "updown")
    assert cache_key in coordinator._observable_cache
    assert len(coordinator._gauge_cache) == 0
    coordinator.meter.create_observable_up_down_counter.assert_called_once_with(
        name="ha.sensor.energy.net",
        callbacks=coordinator.meter.create_observable_up_down_counter.call_args[1][
            "callbacks"
        ],
        description="Home Assistant energy net total sensor",
        unit="kW.h",
    )
    coordinator.meter.create_gauge.assert_not_called()
    coordinator.meter.create_observable_counter.assert_not_called()


async def test_total_increasing_metric_name_has_total_suffix(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that total_increasing sensors get the .total suffix in their metric name."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.gas_meter",
        "42.3",
        attributes={
            "unit_of_measurement": "m³",
            "device_class": "gas",
            "state_class": "total_increasing",
        },
    )

    coordinator._record_metric(state, 42.3)

    assert any(
        name.endswith(".total") for name, _, _ in coordinator._observable_cache
    ), "Expected a .total metric name for total_increasing sensor"


async def test_total_metric_name_has_net_suffix(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that total sensors get the .net suffix in their metric name."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.net_power",
        "150.0",
        attributes={
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "total",
        },
    )

    coordinator._record_metric(state, 150.0)

    assert any(name.endswith(".net") for name, _, _ in coordinator._observable_cache), (
        "Expected a .net metric name for total sensor"
    )


async def test_state_class_included_in_gauge_attributes(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that state_class is present as an attribute on gauge observations."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.temp",
        "20.0",
        attributes={
            "unit_of_measurement": "°C",
            "device_class": "temperature",
            "state_class": "measurement",
        },
    )

    coordinator._record_metric(state, 20.0)

    cache_key = ("ha.sensor.temperature", "Cel")
    gauge = coordinator._gauge_cache[cache_key]
    call_args = gauge.set.call_args
    attrs = call_args[1]["attributes"]
    assert attrs["state_class"] == "measurement"


async def test_observable_counter_latest_value_stored(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that latest value for an observable counter is stored in _latest_observations."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.energy_meter",
        "1000.0",
        attributes={
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
    )

    coordinator._record_metric(state, 1000.0)

    assert "sensor.energy_meter" in coordinator._latest_observations
    stored_value, stored_attrs = coordinator._latest_observations["sensor.energy_meter"]
    assert stored_value == 1000.0
    assert stored_attrs["entity_id"] == "sensor.energy_meter"
    assert stored_attrs["state_class"] == "total_increasing"


async def test_observable_counter_latest_value_updated(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that the latest value in _latest_observations is updated on each state change."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    for reading in [100.0, 200.0, 350.0]:
        state = State(
            "sensor.energy_meter",
            str(reading),
            attributes={
                "unit_of_measurement": "kWh",
                "device_class": "energy",
                "state_class": "total_increasing",
            },
        )
        coordinator._record_metric(state, reading)

    # Only the latest value should be stored
    stored_value, _ = coordinator._latest_observations["sensor.energy_meter"]
    assert stored_value == 350.0
    # Only one observable instrument created despite multiple state changes
    coordinator.meter.create_observable_counter.assert_called_once()


async def test_observable_callback_yields_correct_observations(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that the observable callback yields the correct Observation values."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    state = State(
        "sensor.energy_meter",
        "500.0",
        attributes={
            "unit_of_measurement": "kWh",
            "device_class": "energy",
            "state_class": "total_increasing",
        },
    )

    coordinator._record_metric(state, 500.0)

    # Extract the callback that was registered with create_observable_counter
    create_call = coordinator.meter.create_observable_counter.call_args
    callback = create_call[1]["callbacks"][0]

    # Invoke the callback (simulates SDK collection)
    from opentelemetry.metrics import CallbackOptions

    observations = list(callback(CallbackOptions()))
    assert len(observations) == 1
    obs = observations[0]
    assert obs.value == 500.0
    assert obs.attributes["entity_id"] == "sensor.energy_meter"
    assert obs.attributes["state_class"] == "total_increasing"


async def test_observable_callback_multiple_entities_same_instrument(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that multiple entities sharing the same observable instrument are all yielded."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    for entity_id, value in [
        ("sensor.energy_meter_a", 1000.0),
        ("sensor.energy_meter_b", 2000.0),
    ]:
        state = State(
            entity_id,
            str(value),
            attributes={
                "unit_of_measurement": "kWh",
                "device_class": "energy",
                "state_class": "total_increasing",
            },
        )
        coordinator._record_metric(state, value)

    # Both should share ONE instrument
    assert len(coordinator._observable_cache) == 1
    coordinator.meter.create_observable_counter.assert_called_once()

    # Callback should yield two observations
    create_call = coordinator.meter.create_observable_counter.call_args
    callback = create_call[1]["callbacks"][0]

    from opentelemetry.metrics import CallbackOptions

    observations = list(callback(CallbackOptions()))
    entity_ids = {obs.attributes["entity_id"] for obs in observations}
    assert entity_ids == {"sensor.energy_meter_a", "sensor.energy_meter_b"}


async def test_mixed_state_classes_use_separate_caches(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that measurement and total_increasing sensors for the same device_class
    go into separate caches and use separate instrument types."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    gauge_state = State(
        "sensor.current_power",
        "1500.0",
        attributes={
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "measurement",
        },
    )
    total_state = State(
        "sensor.net_power_total",
        "50000.0",
        attributes={
            "unit_of_measurement": "W",
            "device_class": "power",
            "state_class": "total",
        },
    )

    coordinator._record_metric(gauge_state, 1500.0)
    coordinator._record_metric(total_state, 50000.0)

    # Gauge for measurement
    assert ("ha.sensor.power", "W") in coordinator._gauge_cache
    # UpDownCounter for total
    assert ("ha.sensor.power.net", "W", "updown") in coordinator._observable_cache
    # Different instrument types used
    coordinator.meter.create_gauge.assert_called_once()
    coordinator.meter.create_observable_up_down_counter.assert_called_once()


# ---------------------------------------------------------------------------
# State change routing tests
# ---------------------------------------------------------------------------


async def test_handle_state_change_numeric_routes_to_metric(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test numeric state change routes to _record_metric."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    new_state = State(
        "sensor.temperature",
        "23.5",
        attributes={
            "friendly_name": "Living Room Temperature",
            "unit_of_measurement": "°C",
            "device_class": "temperature",
        },
    )
    event = MagicMock()
    event.data = {"new_state": new_state, "old_state": None}

    coordinator._handle_state_change(event)

    # Gauge must have been created and called
    cache_key = ("ha.sensor.temperature", "Cel")
    assert cache_key in coordinator._gauge_cache
    coordinator._gauge_cache[cache_key].set.assert_called_once()
    call_args = coordinator._gauge_cache[cache_key].set.call_args
    assert call_args[0][0] == 23.5
    assert call_args[1]["attributes"]["entity_id"] == "sensor.temperature"


async def test_handle_state_change_non_numeric_routes_to_log(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test non-numeric state change routes to _record_log."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    mock_logger = MagicMock()
    coordinator.otel_logger = mock_logger

    old_state = State("light.living_room", "off")
    new_state = State(
        "light.living_room",
        "on",
        attributes={"friendly_name": "Living Room Light"},
    )
    event = MagicMock()
    event.data = {"new_state": new_state, "old_state": old_state}

    coordinator._handle_state_change(event)

    mock_logger.emit.assert_called_once()
    log_record = mock_logger.emit.call_args[0][0]
    assert "Living Room Light changed to on" in log_record.body
    assert log_record.attributes["entity_id"] == "light.living_room"
    assert log_record.attributes["new_state"] == "on"
    assert log_record.attributes["old_state"] == "off"
    # Verify SeverityNumber enum is used, not a plain int
    from custom_components.hotel_ax.coordinator import SeverityNumber

    assert log_record.severity_number == SeverityNumber.INFO


async def test_handle_state_change_unavailable_skipped(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that unavailable states are skipped."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    mock_logger = MagicMock()
    coordinator.otel_logger = mock_logger

    new_state = State("sensor.test", "unavailable")
    event = MagicMock()
    event.data = {"new_state": new_state, "old_state": None}

    coordinator._handle_state_change(event)

    mock_logger.emit.assert_not_called()
    assert len(coordinator._gauge_cache) == 0


async def test_handle_state_change_unknown_skipped(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that unknown states are skipped."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    mock_logger = MagicMock()
    coordinator.otel_logger = mock_logger

    new_state = State("sensor.test", "unknown")
    event = MagicMock()
    event.data = {"new_state": new_state, "old_state": None}

    coordinator._handle_state_change(event)

    mock_logger.emit.assert_not_called()
    assert len(coordinator._gauge_cache) == 0


async def test_handle_state_change_empty_skipped(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that empty states are skipped."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    mock_logger = MagicMock()
    coordinator.otel_logger = mock_logger

    new_state = State("sensor.test", "")
    event = MagicMock()
    event.data = {"new_state": new_state, "old_state": None}

    coordinator._handle_state_change(event)

    mock_logger.emit.assert_not_called()
    assert len(coordinator._gauge_cache) == 0


async def test_handle_state_change_error_handled(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that errors in state change handling are caught and don't crash."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    event = MagicMock()
    event.data = {}  # Missing new_state

    # Should not raise exception
    coordinator._handle_state_change(event)


# ---------------------------------------------------------------------------
# Exclusion tests
# ---------------------------------------------------------------------------


async def test_is_excluded_pattern_match(
    hass: HomeAssistant, mock_custom_domain_entry: MockConfigEntry, mock_otel_providers
):
    """Test exclusion pattern matching."""
    mock_custom_domain_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_custom_domain_entry)

    assert coordinator._is_excluded("sensor.excluded_temp") is True
    assert coordinator._is_excluded("sensor.excluded_humidity") is True
    assert coordinator._is_excluded("sensor.included_temp") is False
    assert coordinator._is_excluded("binary_sensor.excluded_motion") is False


async def test_excluded_entity_not_recorded(
    hass: HomeAssistant, mock_custom_domain_entry: MockConfigEntry, mock_otel_providers
):
    """Test that excluded entities produce no metrics or logs."""
    mock_custom_domain_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_custom_domain_entry)

    mock_logger = MagicMock()
    coordinator.otel_logger = mock_logger

    new_state = State("sensor.excluded_temp", "25.0")
    event = MagicMock()
    event.data = {"new_state": new_state, "old_state": None}

    coordinator._handle_state_change(event)

    mock_logger.emit.assert_not_called()
    assert len(coordinator._gauge_cache) == 0


# ---------------------------------------------------------------------------
# Log recording tests
# ---------------------------------------------------------------------------


async def test_record_log_creates_log_record_with_correct_attributes(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test _record_log creates log record with correct attributes."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    mock_logger = MagicMock()
    coordinator.otel_logger = mock_logger

    state = State(
        "switch.outlet",
        "on",
        attributes={
            "friendly_name": "Kitchen Outlet",
            "area_id": "kitchen",
        },
    )

    coordinator._record_log(state, "off", "on")

    mock_logger.emit.assert_called_once()
    log_record = mock_logger.emit.call_args[0][0]
    assert "Kitchen Outlet changed to on" in log_record.body
    assert log_record.attributes["entity_id"] == "switch.outlet"
    assert log_record.attributes["domain"] == "switch"
    assert log_record.attributes["old_state"] == "off"
    assert log_record.attributes["new_state"] == "on"
    assert log_record.attributes["area_id"] == "kitchen"
    # resource is NOT set on the record itself — it is attached by LoggerProvider on emit
    assert not hasattr(log_record, "resource") or log_record.resource is None


# ---------------------------------------------------------------------------
# Cache cleanup tests
# ---------------------------------------------------------------------------


async def test_cache_cleanup_logs_diagnostic(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test cache cleanup logs diagnostic info without crashing."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    # Populate cache with a couple of entries
    coordinator._gauge_cache[("ha.sensor.temperature", "Cel")] = MagicMock()
    coordinator._gauge_cache[("ha.sensor.power", "W")] = MagicMock()

    # Should not raise
    await coordinator._async_cleanup_cache_callback(None)

    # Cache should be unchanged — no pruning by entity existence any more
    assert ("ha.sensor.temperature", "Cel") in coordinator._gauge_cache
    assert ("ha.sensor.power", "W") in coordinator._gauge_cache


# ---------------------------------------------------------------------------
# Exclude pattern parsing tests
# ---------------------------------------------------------------------------


async def test_parse_exclude_patterns_from_config(
    hass: HomeAssistant, mock_otel_providers
):
    """Test that exclude patterns are properly parsed from config."""
    from tests.conftest import MockConfigEntry
    from custom_components.hotel_ax.const import (
        DOMAIN,
        CONF_API_TOKEN,
        CONF_REGION,
        CONF_LOGS_DATASET,
        CONF_METRICS_DATASET,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: "token",
            CONF_REGION: "us-east-1",
            CONF_LOGS_DATASET: "logs",
            CONF_METRICS_DATASET: "metrics",
        },
        options={
            CONF_EXCLUDE_ENTITIES: "sensor.test*, binary_sensor.skip, climate.*",
        },
    )
    entry.add_to_hass(hass)

    coordinator = HotelAXCoordinator(hass, entry)

    assert len(coordinator.exclude_patterns) == 3
    assert "sensor.test*" in coordinator.exclude_patterns
    assert "binary_sensor.skip" in coordinator.exclude_patterns
    assert "climate.*" in coordinator.exclude_patterns


async def test_parse_exclude_patterns_empty_string(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test that empty exclude string results in empty patterns list."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    assert coordinator.exclude_patterns == []


async def test_parse_exclude_patterns_whitespace_handling(
    hass: HomeAssistant, mock_otel_providers
):
    """Test that whitespace in exclude patterns is properly handled."""
    from tests.conftest import MockConfigEntry
    from custom_components.hotel_ax.const import (
        DOMAIN,
        CONF_API_TOKEN,
        CONF_REGION,
        CONF_LOGS_DATASET,
        CONF_METRICS_DATASET,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_API_TOKEN: "token",
            CONF_REGION: "us-east-1",
            CONF_LOGS_DATASET: "logs",
            CONF_METRICS_DATASET: "metrics",
        },
        options={
            CONF_EXCLUDE_ENTITIES: "  sensor.test  ,  binary_sensor.skip  ",
        },
    )
    entry.add_to_hass(hass)

    coordinator = HotelAXCoordinator(hass, entry)

    assert len(coordinator.exclude_patterns) == 2
    assert "sensor.test" in coordinator.exclude_patterns
    assert "binary_sensor.skip" in coordinator.exclude_patterns


# ---------------------------------------------------------------------------
# Integration / end-to-end test
# ---------------------------------------------------------------------------


async def test_integration_full_state_change_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Test full state change flow from HA event bus to gauge recording."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)
    await coordinator.async_start()

    # Fire a state change event on the HA event bus
    hass.states.async_set(
        "sensor.test",
        "42.5",
        {
            "friendly_name": "Test Sensor",
            "unit_of_measurement": "°C",
            "device_class": "temperature",
        },
    )

    await hass.async_block_till_done()

    # Gauge must have been created under the correct UCUM cache key
    cache_key = ("ha.sensor.temperature", "Cel")
    assert cache_key in coordinator._gauge_cache

    await coordinator.async_stop()


# ---------------------------------------------------------------------------
# HA general log forwarding tests
# ---------------------------------------------------------------------------


def _make_ha_logs_entry(
    hass, enabled=True, level="info", dataset="homeassistant-ha-logs"
):
    """Helper to build a config entry with ha_logs settings."""
    from custom_components.hotel_ax.const import (
        DOMAIN,
        CONF_API_TOKEN,
        CONF_REGION,
        CONF_LOGS_DATASET,
        CONF_METRICS_DATASET,
        CONF_HA_LOGS_ENABLED,
        CONF_HA_LOGS_DATASET,
        CONF_HA_LOGS_LEVEL,
    )
    from tests.conftest import MockConfigEntry

    return MockConfigEntry(
        domain=DOMAIN,
        title="Axiom Export",
        data={
            CONF_API_TOKEN: "test-token-123",
            CONF_REGION: "us-east-1",
            CONF_LOGS_DATASET: "homeassistant-logs",
            CONF_METRICS_DATASET: "homeassistant-metrics",
            CONF_HA_LOGS_ENABLED: enabled,
            CONF_HA_LOGS_DATASET: dataset,
            CONF_HA_LOGS_LEVEL: level,
        },
        unique_id="hotel_ax_ha_logs_test",
    )


async def test_ha_logs_disabled_by_default(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """Handler must NOT be attached when ha_logs_enabled is not set (default False)."""
    import logging

    mock_config_entry.add_to_hass(hass)
    before = list(logging.root.handlers)

    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    after = list(logging.root.handlers)
    assert logging.root.handlers == before or coordinator._ha_log_handler is None
    assert coordinator._ha_log_handler is None

    await coordinator.async_stop()


async def test_ha_logs_enabled_attaches_handler(
    hass: HomeAssistant, mock_otel_providers
):
    """When ha_logs_enabled=True the LoggingHandler must be attached to root logger."""
    import logging
    from opentelemetry.sdk._logs import LoggingHandler

    entry = _make_ha_logs_entry(hass, enabled=True)
    entry.add_to_hass(hass)

    before_count = len(logging.root.handlers)
    coordinator = HotelAXCoordinator(hass, entry)

    assert coordinator._ha_log_handler is not None
    assert isinstance(coordinator._ha_log_handler, LoggingHandler)
    assert coordinator._ha_log_handler in logging.root.handlers
    assert len(logging.root.handlers) == before_count + 1

    await coordinator.async_stop()


async def test_ha_logs_handler_removed_on_stop(
    hass: HomeAssistant, mock_otel_providers
):
    """LoggingHandler must be removed from root logger on async_stop()."""
    import logging

    entry = _make_ha_logs_entry(hass, enabled=True)
    entry.add_to_hass(hass)

    coordinator = HotelAXCoordinator(hass, entry)
    handler = coordinator._ha_log_handler
    assert handler in logging.root.handlers

    await coordinator.async_stop()

    assert handler not in logging.root.handlers
    assert coordinator._ha_log_handler is None


async def test_ha_logs_level_warning(hass: HomeAssistant, mock_otel_providers):
    """LoggingHandler level must match configured ha_logs_level=warning."""
    import logging

    entry = _make_ha_logs_entry(hass, enabled=True, level="warning")
    entry.add_to_hass(hass)

    coordinator = HotelAXCoordinator(hass, entry)

    assert coordinator._ha_log_handler is not None
    assert coordinator._ha_log_handler.level == logging.WARNING

    await coordinator.async_stop()


async def test_ha_logs_level_info(hass: HomeAssistant, mock_otel_providers):
    """LoggingHandler level must match configured ha_logs_level=info."""
    import logging

    entry = _make_ha_logs_entry(hass, enabled=True, level="info")
    entry.add_to_hass(hass)

    coordinator = HotelAXCoordinator(hass, entry)

    assert coordinator._ha_log_handler is not None
    assert coordinator._ha_log_handler.level == logging.INFO

    await coordinator.async_stop()


async def test_ha_logs_level_error(hass: HomeAssistant, mock_otel_providers):
    """LoggingHandler level must match configured ha_logs_level=error."""
    import logging

    entry = _make_ha_logs_entry(hass, enabled=True, level="error")
    entry.add_to_hass(hass)

    coordinator = HotelAXCoordinator(hass, entry)

    assert coordinator._ha_log_handler is not None
    assert coordinator._ha_log_handler.level == logging.ERROR

    await coordinator.async_stop()


async def test_ha_logs_dataset_configured(hass: HomeAssistant, mock_otel_providers):
    """ha_logs_dataset must be stored on the coordinator."""
    entry = _make_ha_logs_entry(hass, enabled=True, dataset="my-system-logs")
    entry.add_to_hass(hass)

    coordinator = HotelAXCoordinator(hass, entry)

    assert coordinator.ha_logs_dataset == "my-system-logs"

    await coordinator.async_stop()


async def test_ha_logs_third_exporter_created(hass: HomeAssistant, mock_otel_providers):
    """A separate ha_logger_provider must exist when ha_logs_enabled=True."""
    entry = _make_ha_logs_entry(hass, enabled=True)
    entry.add_to_hass(hass)

    coordinator = HotelAXCoordinator(hass, entry)

    assert hasattr(coordinator, "ha_logger_provider")
    # Must be a different provider from the state-change log provider
    assert coordinator.ha_logger_provider is not coordinator.logger_provider

    await coordinator.async_stop()


async def test_ha_logs_disabled_no_third_provider(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_otel_providers
):
    """No ha_logger_provider must exist when ha_logs_enabled=False (default)."""
    mock_config_entry.add_to_hass(hass)
    coordinator = HotelAXCoordinator(hass, mock_config_entry)

    assert not hasattr(coordinator, "ha_logger_provider")

    await coordinator.async_stop()
