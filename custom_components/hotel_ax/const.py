"""Constants for the Hotel-AX integration."""

DOMAIN = "hotel_ax"

# Axiom edge regions
AXIOM_REGIONS = {
    "us-east-1": "us-east-1.aws.edge.axiom.co",
    "eu-central-1": "eu-central-1.aws.edge.axiom.co",
    "custom": None,  # User-supplied domain
}

AXIOM_REGION_DEFAULT = "us-east-1"

# Configuration keys
CONF_API_TOKEN = "api_token"
CONF_REGION = "region"
CONF_CUSTOM_DOMAIN = "custom_domain"
CONF_LOGS_DATASET = "logs_dataset"
CONF_METRICS_DATASET = "metrics_dataset"
CONF_FLUSH_INTERVAL = "flush_interval"
CONF_EXCLUDE_ENTITIES = "exclude_entities"
CONF_HA_LOGS_ENABLED = "ha_logs_enabled"
CONF_HA_LOGS_DATASET = "ha_logs_dataset"
CONF_HA_LOGS_LEVEL = "ha_logs_level"

# Defaults
DEFAULT_LOGS_DATASET = "homeassistant-logs"
DEFAULT_METRICS_DATASET = "homeassistant-metrics"
DEFAULT_FLUSH_INTERVAL = 30  # seconds
MIN_FLUSH_INTERVAL = 10
MAX_FLUSH_INTERVAL = 300
DEFAULT_HA_LOGS_ENABLED = False
DEFAULT_HA_LOGS_DATASET = "homeassistant-ha-logs"
DEFAULT_HA_LOGS_LEVEL = "info"

HA_LOG_LEVELS = ["debug", "info", "warning", "error", "critical"]

# OTLP endpoints
OTLP_LOGS_PATH = "/v1/logs"
OTLP_METRICS_PATH = "/v1/metrics"
OTLP_TRACES_PATH = "/v1/traces"
