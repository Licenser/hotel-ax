"""Coordinator for Hotel-AX integration."""

from __future__ import annotations

import asyncio
import fnmatch
import logging
from datetime import timedelta
from typing import Any

from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.metrics import CallbackOptions, Observation
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor

# Import LogRecord and SeverityNumber from the correct location depending on version
try:
    # Newer OpenTelemetry SDK versions (1.21+)
    from opentelemetry.sdk._logs._internal import LogRecord as OTelLogRecord
    from opentelemetry.sdk._logs._internal import SeverityNumber
except ImportError:
    try:
        from opentelemetry.sdk._logs import LogRecord as OTelLogRecord
        from opentelemetry.sdk._logs import SeverityNumber
    except ImportError:
        from opentelemetry.sdk._logs._log_record import LogRecord as OTelLogRecord
        from opentelemetry.sdk._logs._log_record import SeverityNumber

from opentelemetry.semconv.resource import ResourceAttributes

# Import _time_ns from the correct location depending on OpenTelemetry version
try:
    # Try newer OpenTelemetry SDK versions
    from opentelemetry.sdk.util import _time_ns
except ImportError:
    try:
        # Try older versions
        from opentelemetry.util._time import _time_ns
    except ImportError:
        # Fallback - use time module directly
        import time

        def _time_ns():
            return int(time.time() * 1e9)


from homeassistant.const import EVENT_STATE_CHANGED
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.event import async_track_time_interval

from .const import (
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
    OTLP_LOGS_PATH,
    OTLP_METRICS_PATH,
    AXIOM_REGIONS,
)

_LOGGER = logging.getLogger(__name__)

# Mapping from Home Assistant unit_of_measurement strings to UCUM case-sensitive codes.
# Source of truth: https://ucum.org/ucum (UCUM c/s column)
# Per OTEL semantic conventions, instrument units SHOULD follow UCUM c/s codes.
# OTEL spec: unit MUST be ASCII, max 63 chars.
_HA_UNIT_TO_UCUM: dict[str, str] = {
    # Temperature — special units (non-ratio/interval scale) in UCUM
    "°C": "Cel",
    "°F": "[degF]",
    "K": "K",
    # Percentage / dimensionless
    "%": "%",
    "ppm": "[ppm]",
    "ppb": "[ppb]",
    "UV index": "1",
    # Power
    "mW": "mW",
    "W": "W",
    "kW": "kW",
    "MW": "MW",
    "GW": "GW",
    "TW": "TW",
    "BTU/h": "[BTU_IT]/h",
    # Apparent power
    "VA": "V.A",
    "kVA": "kV.A",
    "mVA": "mV.A",
    # Reactive power
    "var": "V.A",
    "kvar": "kV.A",
    "mvar": "mV.A",
    # Energy
    "J": "J",
    "kJ": "kJ",
    "MJ": "MJ",
    "GJ": "GJ",
    "Wh": "W.h",
    "mWh": "mW.h",
    "kWh": "kW.h",
    "MWh": "MW.h",
    "GWh": "GW.h",
    "TWh": "TW.h",
    "cal": "cal",
    "kcal": "kcal",
    # Voltage
    "μV": "uV",
    "mV": "mV",
    "V": "V",
    "kV": "kV",
    "MV": "MV",
    # Current
    "mA": "mA",
    "A": "A",
    # Frequency
    "Hz": "Hz",
    "kHz": "kHz",
    "MHz": "MHz",
    "GHz": "GHz",
    # Pressure
    "mPa": "mPa",
    "Pa": "Pa",
    "hPa": "hPa",
    "kPa": "kPa",
    "bar": "bar",
    "cbar": "cbar",
    "mbar": "mbar",
    "mmHg": "mm[Hg]",
    "inHg": "[in_i'Hg]",
    "inH₂O": "[in_i'H2O]",
    "psi": "[psi]",
    # Length
    "mm": "mm",
    "cm": "cm",
    "m": "m",
    "km": "km",
    "in": "[in_i]",
    "ft": "[ft_i]",
    "yd": "[yd_i]",
    "mi": "[mi_i]",
    "nmi": "[nmi_i]",
    # Area — UCUM uses superscript notation via exponents
    "m²": "m2",
    "cm²": "cm2",
    "km²": "km2",
    "mm²": "mm2",
    "in²": "[in_i]2",
    "ft²": "[sft_i]",
    "yd²": "[yd_i]2",
    "mi²": "[mi_i]2",
    "ac": "[acr_us]",
    "ha": "har",
    # Volume
    "L": "L",
    "mL": "mL",
    "m³": "m3",
    "ft³": "[cft_i]",
    "CCF": "100.[cft_i]",
    "gal": "[gal_us]",
    "fl. oz.": "[foz_us]",
    # Volume flow rate
    "m³/h": "m3/h",
    "m³/min": "m3/min",
    "m³/s": "m3/s",
    "ft³/min": "[cft_i]/min",
    "L/h": "L/h",
    "L/min": "L/min",
    "L/s": "L/s",
    "mL/s": "mL/s",
    "gal/h": "[gal_us]/h",
    "gal/min": "[gal_us]/min",
    "gal/d": "[gal_us]/d",
    # Mass
    "g": "g",
    "mg": "mg",
    "μg": "ug",
    "kg": "kg",
    "oz": "[oz_av]",
    "lb": "[lb_av]",
    "st": "[stone_av]",
    # Conductivity
    "S/cm": "S/cm",
    "μS/cm": "uS/cm",
    "mS/cm": "mS/cm",
    # Illuminance / luminous flux
    "lx": "lx",
    "lm": "lm",
    # Sound / signal
    "dB": "dB",
    "dBA": "dB",  # A-weighted dB, no UCUM code — use dB as best approximation
    "dBm": "dB[mW]",
    # Concentration
    "g/m³": "g/m3",
    "mg/m³": "mg/m3",
    "μg/m³": "ug/m3",
    "μg/ft³": "ug/[cft_i]",
    "p/m³": "{particles}/m3",
    "mg/dL": "mg/dL",
    "mmol/L": "mmol/L",
    # Speed
    "m/s": "m/s",
    "m/min": "m/min",
    "km/h": "km/h",
    "mph": "[mph_i]",
    "ft/s": "[ft_i]/s",
    "in/s": "[in_i]/s",
    "mm/s": "mm/s",
    "kn": "kn",
    # Time
    "μs": "us",
    "ms": "ms",
    "s": "s",
    "min": "min",
    "h": "h",
    "d": "d",
    "w": "wk",
    # Precipitation
    "mm/h": "mm/h",
    "mm/d": "mm/d",
    "in/h": "[in_i]/h",
    "in/d": "[in_i]/d",
    # Irradiance
    "W/m²": "W/m2",
    "BTU/(h⋅ft²)": "[BTU_IT]/h/[sft_i]",
    # Data (information)
    "bit": "bit",
    "kbit": "kbit",
    "Mbit": "Mbit",
    "Gbit": "Gbit",
    "B": "By",
    "kB": "kBy",
    "MB": "MBy",
    "GB": "GBy",
    "TB": "TBy",
    "PB": "PBy",
    "KiB": "KiBy",
    "MiB": "MiBy",
    "GiB": "GiBy",
    "TiB": "TiBy",
    # Data rate
    "bit/s": "bit/s",
    "kbit/s": "kbit/s",
    "Mbit/s": "Mbit/s",
    "Gbit/s": "Gbit/s",
    "B/s": "By/s",
    "kB/s": "kBy/s",
    "MB/s": "MBy/s",
    "GB/s": "GBy/s",
    "KiB/s": "KiBy/s",
    "MiB/s": "MiBy/s",
    "GiB/s": "GiBy/s",
    # Angle
    "°": "deg",
    # Energy distance
    "kWh/100km": "kW.h/(100.km)",
    "Wh/km": "W.h/km",
    "mi/kWh": "[mi_i]/kW.h",
    "km/kWh": "km/kW.h",
    # Misc
    "rpm": "{rev}/min",
    "VA": "V.A",
    "varh": "V.A.h",
    "kvarh": "kV.A.h",
}


def _ha_unit_to_ucum(ha_unit: str) -> str:
    """Convert a Home Assistant unit_of_measurement string to a UCUM c/s code.

    Returns a valid OTEL instrument unit: ASCII string, max 63 characters.
    Falls back to stripping non-ASCII characters for unknown units.
    Uses '1' (dimensionless) if no valid unit can be derived.
    """
    if not ha_unit:
        return "1"

    # Direct lookup first
    ucum = _HA_UNIT_TO_UCUM.get(ha_unit)
    if ucum is not None:
        return ucum[:63]

    # Fallback: strip non-ASCII characters and truncate
    ascii_unit = ha_unit.encode("ascii", errors="ignore").decode("ascii").strip()
    if ascii_unit:
        return ascii_unit[:63]

    # Nothing usable — dimensionless
    return "1"


class HotelAXCoordinator:
    """Coordinator to manage OTLP exports to Axiom."""

    def __init__(self, hass: HomeAssistant, entry: Any) -> None:
        """Initialize the coordinator."""
        self.hass = hass
        self.entry = entry
        self._unsub_state_listener = None
        self._unsub_flush_interval = None
        self._unsub_cache_cleanup = None

        # Get config
        self.config = {**entry.data, **entry.options}

        # Determine the Axiom domain
        region = self.config.get(CONF_REGION)
        if region == "custom":
            self.axiom_domain = self.config.get(CONF_CUSTOM_DOMAIN)
        else:
            self.axiom_domain = AXIOM_REGIONS.get(region)

        if not self.axiom_domain:
            raise ValueError("No valid Axiom domain configured")

        self.api_token = self.config[CONF_API_TOKEN]
        self.logs_dataset = self.config[CONF_LOGS_DATASET]
        self.metrics_dataset = self.config[CONF_METRICS_DATASET]
        self.flush_interval = self.config.get(
            CONF_FLUSH_INTERVAL, DEFAULT_FLUSH_INTERVAL
        )

        # HA general log forwarding config
        self.ha_logs_enabled = self.config.get(
            CONF_HA_LOGS_ENABLED, DEFAULT_HA_LOGS_ENABLED
        )
        self.ha_logs_dataset = self.config.get(
            CONF_HA_LOGS_DATASET, DEFAULT_HA_LOGS_DATASET
        )
        self.ha_logs_level = self.config.get(CONF_HA_LOGS_LEVEL, DEFAULT_HA_LOGS_LEVEL)

        # Parse exclusion patterns
        exclude_str = self.config.get(CONF_EXCLUDE_ENTITIES, "")
        self.exclude_patterns = [p.strip() for p in exclude_str.split(",") if p.strip()]

        # Holder for the root-logger handler (set in _init_exporters if enabled)
        self._ha_log_handler: LoggingHandler | None = None

        # Resource attributes (service info)
        # Get HA version - try multiple methods for compatibility
        ha_version = "unknown"
        try:
            from homeassistant.const import __version__ as HA_VERSION

            ha_version = HA_VERSION
        except ImportError:
            try:
                import homeassistant

                ha_version = homeassistant.__version__
            except (ImportError, AttributeError):
                pass

        self.resource = Resource.create(
            {
                ResourceAttributes.SERVICE_NAME: "home-assistant",
                ResourceAttributes.SERVICE_VERSION: ha_version,
                ResourceAttributes.HOST_NAME: hass.config.location_name,
            }
        )

        # Initialize OTLP exporters
        self._init_exporters()

        # Cache for gauge instruments keyed by (metric_name, ucum_unit).
        # Multiple entities with the same device_class and unit share one gauge;
        # individual time series are distinguished by attributes on each set() call.
        # No lock needed — @callback ensures sequential execution on the event loop.
        self._gauge_cache: dict[tuple[str, str], Any] = {}

        # Cache for observable counter/updown-counter instruments keyed by
        # (metric_name, ucum_unit, instrument_kind) where instrument_kind is
        # "counter" (total_increasing) or "updown" (total).
        self._observable_cache: dict[tuple[str, str, str], Any] = {}

        # Latest observed value and attributes per entity_id, read by observable
        # callbacks when the SDK collects metrics. Keyed by entity_id, value is
        # (numeric_value, attributes_dict).  Written by @callback (single-threaded
        # event loop), read by SDK collection thread — a plain dict is safe here
        # because Python dict reads/writes on CPython are atomic at the GIL level.
        self._latest_observations: dict[str, tuple[float, dict]] = {}

        _LOGGER.info(
            "Hotel-AX coordinator initialized: domain=%s, logs_dataset=%s, metrics_dataset=%s, ha_logs_enabled=%s",
            self.axiom_domain,
            self.logs_dataset,
            self.metrics_dataset,
            self.ha_logs_enabled,
        )

    def _init_exporters(self) -> None:
        """Initialize OTLP metric and log exporters."""
        # Headers for Axiom
        metrics_headers = {
            "Authorization": f"Bearer {self.api_token}",
            "X-Axiom-Dataset": self.metrics_dataset,
        }
        logs_headers = {
            "Authorization": f"Bearer {self.api_token}",
            "X-Axiom-Dataset": self.logs_dataset,
        }

        # Metric exporter
        metrics_endpoint = f"https://{self.axiom_domain}{OTLP_METRICS_PATH}"
        self.metric_exporter = OTLPMetricExporter(
            endpoint=metrics_endpoint,
            headers=metrics_headers,
        )

        # Log exporter
        logs_endpoint = f"https://{self.axiom_domain}{OTLP_LOGS_PATH}"
        self.log_exporter = OTLPLogExporter(
            endpoint=logs_endpoint,
            headers=logs_headers,
        )

        # Set up MeterProvider for metrics
        metric_reader = PeriodicExportingMetricReader(
            self.metric_exporter,
            export_interval_millis=self.flush_interval * 1000,
        )
        self.meter_provider = MeterProvider(
            resource=self.resource,
            metric_readers=[metric_reader],
        )
        self.meter = self.meter_provider.get_meter("hotel_ax")

        # Set up LoggerProvider for state-change logs
        self.logger_provider = LoggerProvider(resource=self.resource)
        self.logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(self.log_exporter)
        )
        self.otel_logger = self.logger_provider.get_logger("hotel_ax")

        # Set up HA general log forwarding (optional)
        self._ha_log_handler = None
        if self.ha_logs_enabled:
            ha_logs_headers = {
                "Authorization": f"Bearer {self.api_token}",
                "X-Axiom-Dataset": self.ha_logs_dataset,
            }
            ha_logs_endpoint = f"https://{self.axiom_domain}{OTLP_LOGS_PATH}"
            self.ha_log_exporter = OTLPLogExporter(
                endpoint=ha_logs_endpoint,
                headers=ha_logs_headers,
            )
            self.ha_logger_provider = LoggerProvider(resource=self.resource)
            self.ha_logger_provider.add_log_record_processor(
                BatchLogRecordProcessor(self.ha_log_exporter)
            )
            log_level = getattr(logging, self.ha_logs_level.upper(), logging.INFO)
            self._ha_log_handler = LoggingHandler(
                level=log_level,
                logger_provider=self.ha_logger_provider,
            )
            logging.root.addHandler(self._ha_log_handler)
            _LOGGER.debug(
                "HA general log forwarding enabled: dataset=%s, level=%s",
                self.ha_logs_dataset,
                self.ha_logs_level,
            )

        _LOGGER.debug("OTLP exporters initialized")

    async def async_start(self) -> None:
        """Start listening to state changes and schedule flush."""
        # Subscribe to all state changes
        self._unsub_state_listener = self.hass.bus.async_listen(
            EVENT_STATE_CHANGED, self._handle_state_change
        )

        # Schedule periodic manual flush check (backup to OTLP's own scheduling)
        self._unsub_flush_interval = async_track_time_interval(
            self.hass,
            self._async_flush_callback,
            timedelta(seconds=self.flush_interval),
        )

        # Schedule periodic cache cleanup (every hour)
        self._unsub_cache_cleanup = async_track_time_interval(
            self.hass,
            self._async_cleanup_cache_callback,
            timedelta(hours=1),
        )

        _LOGGER.info("Hotel-AX coordinator started")

    async def async_stop(self) -> None:
        """Stop the coordinator and flush remaining data."""
        # Flush BEFORE unsubscribing to capture final state changes
        await self.async_flush()

        if self._unsub_state_listener:
            self._unsub_state_listener()
            self._unsub_state_listener = None

        if self._unsub_flush_interval:
            self._unsub_flush_interval()
            self._unsub_flush_interval = None

        if self._unsub_cache_cleanup:
            self._unsub_cache_cleanup()
            self._unsub_cache_cleanup = None

        # Detach HA general log handler before shutdown to stop capturing logs
        if self._ha_log_handler is not None:
            logging.root.removeHandler(self._ha_log_handler)
            self._ha_log_handler = None

        # Shutdown providers
        if hasattr(self, "meter_provider"):
            await self.hass.async_add_executor_job(self.meter_provider.shutdown)
        if hasattr(self, "logger_provider"):
            await self.hass.async_add_executor_job(self.logger_provider.shutdown)
        if hasattr(self, "ha_logger_provider"):
            await self.hass.async_add_executor_job(self.ha_logger_provider.shutdown)

        _LOGGER.info("Hotel-AX coordinator stopped")

    @callback
    def _handle_state_change(self, event: Event) -> None:
        """Handle a state change event."""
        entity_id = "unknown"
        try:
            new_state = event.data.get("new_state")
            old_state = event.data.get("old_state")

            if new_state is None:
                return

            entity_id = new_state.entity_id

            # Check exclusion patterns early
            if self._is_excluded(entity_id):
                return

            domain = entity_id.split(".")[0]
            state_str = new_state.state

            # Skip unavailable/unknown states
            if state_str in ("unavailable", "unknown", ""):
                return

            # Try to parse as numeric -> metric
            try:
                numeric_value = float(state_str)
                self._record_metric(new_state, numeric_value)
            except (ValueError, TypeError):
                # Non-numeric -> log event (always log all non-numeric state changes)
                old_state_str = (
                    old_state.state
                    if (old_state and old_state.state is not None)
                    else "unknown"
                )
                self._record_log(new_state, old_state_str, state_str)
        except Exception as err:
            _LOGGER.error(
                "Error handling state change for %s: %s",
                entity_id,
                err,
                exc_info=True,
            )

    def _is_excluded(self, entity_id: str) -> bool:
        """Check if entity matches any exclusion pattern."""
        for pattern in self.exclude_patterns:
            if fnmatch.fnmatch(entity_id, pattern):
                return True
        return False

    def _record_metric(self, state, value: float) -> None:
        """Record a numeric state as the appropriate OTLP metric instrument.

        Routing is based on the HA ``state_class`` attribute:

        +-----------------------+-----------------------------+---------------------------+
        | state_class           | OTEL instrument             | metric name suffix        |
        +-----------------------+-----------------------------+---------------------------+
        | measurement           | Gauge                       | (none)                    |
        | measurement_angle     | Gauge                       | (none)                    |
        | total_increasing      | ObservableCounter           | .total                    |
        | total                 | ObservableUpDownCounter     | .net                      |
        | (missing / unknown)   | Gauge (fallback)            | (none)                    |
        +-----------------------+-----------------------------+---------------------------+

        Metric naming follows OTEL semantic conventions:
        - name describes *what* is measured (ha.sensor.<device_class>[.<suffix>])
        - unit uses UCUM c/s codes (ASCII, max 63 chars)
        - attributes identify *which* entity produced the measurement
        """
        state_class = state.attributes.get("state_class", "") or ""

        if state_class == "total_increasing":
            self._record_observable_counter(state, value)
        elif state_class == "total":
            self._record_observable_up_down_counter(state, value)
        else:
            # measurement, measurement_angle, or missing → Gauge
            self._record_gauge(state, value)

    def _build_metric_attributes(
        self,
        state,
        value: float,
        domain: str,
        device_class: str,
        ha_unit: str,
        state_class: str,
    ) -> dict:
        """Build the standard attribute dict for a metric data point."""
        return {
            "entity_id": state.entity_id,
            "domain": domain,
            "device_class": device_class,
            "friendly_name": state.attributes.get("friendly_name", state.entity_id),
            "area_id": state.attributes.get("area_id", "") or "",
            "unit_of_measurement": ha_unit,
            "state_class": state_class,
        }

    def _record_gauge(self, state, value: float) -> None:
        """Record a numeric state as an OTLP Gauge (instantaneous measurement).

        All instruments with the same name must share the same unit — so we
        key both the name and the cache on (metric_name, ucum_unit).
        """
        entity_id = state.entity_id
        ha_unit = state.attributes.get("unit_of_measurement", "") or ""
        device_class = state.attributes.get("device_class", "") or ""
        state_class = state.attributes.get("state_class", "") or ""
        domain = entity_id.split(".")[0]

        # Convert HA unit to UCUM
        ucum_unit = _ha_unit_to_ucum(ha_unit)

        # Metric name: ha.sensor.<device_class> or ha.sensor.<domain> if no device_class.
        classifier = device_class if device_class else domain
        metric_name = f"ha.sensor.{classifier}"

        # Get or create the shared gauge for this (name, unit) combination.
        cache_key = (metric_name, ucum_unit)
        if cache_key not in self._gauge_cache:
            self._gauge_cache[cache_key] = self.meter.create_gauge(
                name=metric_name,
                description=f"Home Assistant {classifier} sensor",
                unit=ucum_unit,
            )

        gauge = self._gauge_cache[cache_key]

        # Record the observation. entity_id in attributes provides the individual
        # time series — this is the correct OTEL pattern for high-cardinality labels.
        gauge.set(
            value,
            attributes=self._build_metric_attributes(
                state, value, domain, device_class, ha_unit, state_class
            ),
        )

        _LOGGER.debug(
            "Recorded gauge metric: %s = %s %s (ucum: %s)",
            entity_id,
            value,
            ha_unit,
            ucum_unit,
        )

    def _record_observable_counter(self, state, value: float) -> None:
        """Record a total_increasing sensor as an OTLP ObservableCounter.

        The ObservableCounter maps to a cumulative monotonic Sum in OTLP.
        The callback yields the latest absolute value; the SDK handles
        start-time bookkeeping and cumulative-vs-delta conversion.

        Metric name: ``ha.sensor.<device_class>.total``
        """
        entity_id = state.entity_id
        ha_unit = state.attributes.get("unit_of_measurement", "") or ""
        device_class = state.attributes.get("device_class", "") or ""
        state_class = state.attributes.get("state_class", "") or ""
        domain = entity_id.split(".")[0]

        ucum_unit = _ha_unit_to_ucum(ha_unit)
        classifier = device_class if device_class else domain
        metric_name = f"ha.sensor.{classifier}.total"

        # Store latest value so the callback can yield it
        self._latest_observations[entity_id] = (
            value,
            self._build_metric_attributes(
                state, value, domain, device_class, ha_unit, state_class
            ),
        )

        cache_key = (metric_name, ucum_unit, "counter")
        if cache_key not in self._observable_cache:
            # Build a callback that captures this cache_key so it can find all
            # entity_ids whose observations belong to this instrument.
            def _make_callback(key: tuple) -> Any:
                def _callback(_options: CallbackOptions):
                    for eid, (val, attrs) in self._latest_observations.items():
                        # Only yield if this entity maps to the same instrument key
                        _ha_unit = attrs.get("unit_of_measurement", "") or ""
                        _dc = attrs.get("device_class", "") or ""
                        _domain = attrs.get("domain", "") or ""
                        _cls = _dc if _dc else _domain
                        _sc = attrs.get("state_class", "") or ""
                        if _sc == "total_increasing":
                            _name = f"ha.sensor.{_cls}.total"
                            _unit = _ha_unit_to_ucum(_ha_unit)
                            if (_name, _unit, "counter") == key:
                                yield Observation(val, attrs)

                return _callback

            self._observable_cache[cache_key] = self.meter.create_observable_counter(
                name=metric_name,
                callbacks=[_make_callback(cache_key)],
                description=f"Home Assistant {classifier} cumulative total sensor",
                unit=ucum_unit,
            )

        _LOGGER.debug(
            "Recorded observable counter: %s = %s %s (ucum: %s)",
            entity_id,
            value,
            ha_unit,
            ucum_unit,
        )

    def _record_observable_up_down_counter(self, state, value: float) -> None:
        """Record a total sensor as an OTLP ObservableUpDownCounter.

        The ObservableUpDownCounter maps to a cumulative non-monotonic Sum in OTLP.
        Values can increase or decrease (e.g. net energy import/export).

        Metric name: ``ha.sensor.<device_class>.net``
        """
        entity_id = state.entity_id
        ha_unit = state.attributes.get("unit_of_measurement", "") or ""
        device_class = state.attributes.get("device_class", "") or ""
        state_class = state.attributes.get("state_class", "") or ""
        domain = entity_id.split(".")[0]

        ucum_unit = _ha_unit_to_ucum(ha_unit)
        classifier = device_class if device_class else domain
        metric_name = f"ha.sensor.{classifier}.net"

        # Store latest value so the callback can yield it
        self._latest_observations[entity_id] = (
            value,
            self._build_metric_attributes(
                state, value, domain, device_class, ha_unit, state_class
            ),
        )

        cache_key = (metric_name, ucum_unit, "updown")
        if cache_key not in self._observable_cache:

            def _make_callback(key: tuple) -> Any:
                def _callback(_options: CallbackOptions):
                    for eid, (val, attrs) in self._latest_observations.items():
                        _ha_unit = attrs.get("unit_of_measurement", "") or ""
                        _dc = attrs.get("device_class", "") or ""
                        _domain = attrs.get("domain", "") or ""
                        _cls = _dc if _dc else _domain
                        _sc = attrs.get("state_class", "") or ""
                        if _sc == "total":
                            _name = f"ha.sensor.{_cls}.net"
                            _unit = _ha_unit_to_ucum(_ha_unit)
                            if (_name, _unit, "updown") == key:
                                yield Observation(val, attrs)

                return _callback

            self._observable_cache[cache_key] = (
                self.meter.create_observable_up_down_counter(
                    name=metric_name,
                    callbacks=[_make_callback(cache_key)],
                    description=f"Home Assistant {classifier} net total sensor",
                    unit=ucum_unit,
                )
            )

        _LOGGER.debug(
            "Recorded observable up-down counter: %s = %s %s (ucum: %s)",
            entity_id,
            value,
            ha_unit,
            ucum_unit,
        )

    def _record_log(self, state, old_state: str, new_state: str) -> None:
        """Record a non-numeric state change as an OTLP log."""
        entity_id = state.entity_id
        friendly_name = state.attributes.get("friendly_name", entity_id)
        area_id = state.attributes.get("area_id", "")
        domain = entity_id.split(".")[0]

        body = f"{friendly_name} changed to {new_state}"

        # Emit log record
        self.otel_logger.emit(
            self._create_log_record(
                body=body,
                severity_number=SeverityNumber.INFO,
                severity_text="INFO",
                attributes={
                    "entity_id": entity_id,
                    "domain": domain,
                    "old_state": old_state,
                    "new_state": new_state,
                    "friendly_name": friendly_name,
                    "area_id": area_id,
                },
            )
        )

        _LOGGER.debug(
            "Recorded log: %s changed from %s to %s", entity_id, old_state, new_state
        )

    def _create_log_record(
        self,
        body: str,
        severity_number: Any,
        severity_text: str,
        attributes: dict[str, Any],
    ) -> Any:
        """Create an OTLP log record.

        Note: resource is NOT passed here — it is attached by the LoggerProvider
        when the record is emitted via otel_logger.emit(). Passing resource as a
        constructor argument is not supported in newer OTEL SDK versions.
        """
        return OTelLogRecord(
            timestamp=_time_ns(),
            body=body,
            severity_number=severity_number,
            severity_text=severity_text,
            attributes=attributes,
        )

    async def _async_flush_callback(self, _now) -> None:
        """Periodic flush callback."""
        await self.async_flush()

    async def _async_cleanup_cache_callback(self, _now) -> None:
        """Periodic cache cleanup.

        Instruments are keyed by (metric_name, ucum_unit[, kind]) and shared across
        entities, so we can't prune by entity existence.  We log cache sizes for
        diagnostics — in practice the number of unique (device_class, unit) pairs is
        small and bounded (dozens at most), so growth is not a concern.
        """
        try:
            _LOGGER.debug(
                "Gauge cache: %d instrument(s): %s",
                len(self._gauge_cache),
                [f"{name}[{unit}]" for name, unit in self._gauge_cache],
            )
            _LOGGER.debug(
                "Observable cache: %d instrument(s): %s",
                len(self._observable_cache),
                [
                    f"{name}[{unit}]({kind})"
                    for name, unit, kind in self._observable_cache
                ],
            )
            _LOGGER.debug(
                "Latest observations tracked: %d entity/entities",
                len(self._latest_observations),
            )
        except Exception as err:
            _LOGGER.error("Error during cache check: %s", err, exc_info=True)

    async def async_flush(self) -> None:
        """Flush both metrics and logs buffers."""
        # Force flush to ensure data is exported before shutdown
        try:
            if hasattr(self, "meter_provider"):
                await self.hass.async_add_executor_job(
                    lambda: self.meter_provider.force_flush(timeout_millis=30000)
                )
            if hasattr(self, "logger_provider"):
                await self.hass.async_add_executor_job(
                    lambda: self.logger_provider.force_flush(timeout_millis=30000)
                )
            if hasattr(self, "ha_logger_provider"):
                await self.hass.async_add_executor_job(
                    lambda: self.ha_logger_provider.force_flush(timeout_millis=30000)
                )
            _LOGGER.debug("Flush completed successfully")
        except Exception as err:
            _LOGGER.error("Error during flush: %s", err, exc_info=True)
