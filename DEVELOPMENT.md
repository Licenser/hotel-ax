# Hotel-AX Development Guide

## Project structure

```
hotel-ax/
├── custom_components/
│   └── hotel_ax/                    # Integration code
│       ├── __init__.py               # Entry point (setup/teardown)
│       ├── manifest.json             # HA + HACS metadata
│       ├── config_flow.py            # 3-step setup wizard
│       ├── options_flow.py           # Reconfiguration UI
│       ├── coordinator.py            # Core logic: event listener + OTLP export
│       ├── const.py                  # Constants and configuration keys
│       ├── strings.json              # UI label keys
│       └── translations/
│           └── en.json               # English translations
├── brand/
│   ├── icon.png                      # 256x256 icon (YOU NEED TO CREATE THIS)
│   └── ICON_README.md                # Icon requirements
├── hacs.json                         # HACS metadata
├── README.md                         # User documentation
└── .gitignore
```

## Running tests

### Automated test suite

The integration has a comprehensive test suite covering:
- Config flow (3-step wizard, validation, error handling)
- Options flow (reconfiguration)
- Coordinator (state routing, caching, exclusions, flush)
- Integration lifecycle (setup/unload/reload)

**Run all tests:**

```bash
./run_tests.sh
```

Or manually:

```bash
# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements-dev.txt

# Run tests
pytest

# Run with coverage
pytest --cov=custom_components/hotel_ax --cov-report=html

# Run specific test file
pytest tests/test_config_flow.py -v
```

### CI/CD

Tests run automatically on GitHub Actions for:
- Python 3.11 and 3.12
- Linting (ruff, black, isort)
- HACS validation

See `.github/workflows/ci.yml` for details.

## Testing manually in Home Assistant

### 1. Copy to Home Assistant

```bash
# From this repo root
cp -r custom_components/hotel_ax /path/to/homeassistant/custom_components/
```

### 2. Restart Home Assistant

```bash
# Via SSH or container
ha core restart
# or
docker restart homeassistant
```

### 3. Add the integration

1. Go to **Settings** → **Devices & Services**
2. Click **Add Integration**
3. Search for **Hotel-AX**
4. Follow the config wizard

### 4. Check logs

Enable debug logging in `configuration.yaml`:

```yaml
logger:
  default: info
  logs:
    custom_components.hotel_ax: debug
```

Then check logs in **Settings** → **System** → **Logs** or via CLI:

```bash
tail -f /config/home-assistant.log | grep hotel_ax
```

## Publishing to GitHub

### 1. Create the repository

```bash
git init
git add .
git commit -m "Initial commit: Hotel-AX integration"
gh repo create Licenser/hotel-ax --public --source=. --remote=origin
git push -u origin main
```

### 2. Create a release

```bash
git tag v0.1.0
git push origin v0.1.0
```

Then create a GitHub release via the web UI with tag `v0.1.0`.

### 3. Add to HACS

Users can install via **HACS** → **Integrations** → **Custom repositories** → Add `https://github.com/Licenser/hotel-ax`.

Optionally, submit to the [HACS default store](https://github.com/hacs/default) via PR.

## Key implementation notes

### Coordinator logic (coordinator.py)

- Subscribes to `EVENT_STATE_CHANGED` in HA event bus
- For each state change:
  - Numeric → `_record_metric()` → OTLP Gauge
  - Non-numeric → `_record_log()` → OTLP LogRecord
- Uses OpenTelemetry SDK's built-in batching:
  - `PeriodicExportingMetricReader` for metrics
  - `BatchLogRecordProcessor` for logs
- Flush interval is configurable (default 30s)

### OTLP endpoints

- Logs: `https://{domain}/v1/logs` with `X-Axiom-Dataset: {logs_dataset}`
- Metrics: `https://{domain}/v1/metrics` with `X-Axiom-Dataset: {metrics_dataset}`
- Metrics endpoint only accepts `application/x-protobuf` (no JSON)

### Config flow

Three steps:
1. `async_step_user` → API token + region dropdown
2. `async_step_custom_domain` → custom domain (only if "Custom" selected)
3. `async_step_datasets` → logs + metrics dataset names, validates connection

### Options flow

Single-step reconfiguration form with all settings exposed.

## Dependencies

From `manifest.json`:

```json
"requirements": [
  "opentelemetry-sdk==1.40.0",
  "opentelemetry-exporter-otlp-proto-http==1.40.0"
]
```

Home Assistant automatically installs these when the integration loads.

## HACS requirements checklist

- [x] `custom_components/hotel_ax/` directory
- [x] `manifest.json` with `domain`, `documentation`, `issue_tracker`, `codeowners`, `name`, `version`
- [x] `hacs.json` at repo root
- [x] `README.md`
- [ ] `brand/icon.png` (256x256 PNG) — **YOU NEED TO CREATE THIS**
- [x] GitHub releases with semver tags

## TODO before first release

1. **Create `brand/icon.png`** — see `brand/ICON_README.md` for requirements
2. Test the integration with a real Home Assistant instance + Axiom account
3. Verify metrics and logs appear in Axiom
4. Test the config flow validation
5. Test the options flow (reconfiguration)
6. Create GitHub repo and push
7. Create `v0.1.0` release
8. Update README with actual GitHub URLs
9. (Optional) Submit to HACS default store

## Known limitations

- Single Axiom account per HA instance (enforced via unique_id)
- No retry logic for failed exports (buffers are cleared on error)
- No support for OTLP traces (only logs + metrics)
- Metrics dataset must support protobuf format (Axiom requirement)

## Future enhancements

- Support for OTLP traces
- Configurable retry/backoff for failed exports
- Per-domain log level configuration
- Entity attribute filtering
- Sampling for high-frequency sensors
- Dashboard card showing export stats
