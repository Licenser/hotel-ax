# Hotel-AX Test Suite

Comprehensive test coverage for the Hotel-AX Home Assistant integration.

## Test Files

| File | Coverage | Test Count |
|------|----------|------------|
| `test_config_flow.py` | Config flow (3-step wizard, validation, errors) | 17 tests |
| `test_options_flow.py` | Options flow (reconfiguration UI) | 11 tests |
| `test_coordinator.py` | Coordinator (state routing, caching, exclusions) | 20+ tests |
| `test_init.py` | Integration lifecycle (setup/unload/reload) | 8 tests |

## Running Tests

### Quick start

```bash
./run_tests.sh
```

### Manual execution

```bash
# Install dependencies
pip install -r requirements-dev.txt

# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_config_flow.py -v

# Run with coverage report
pytest --cov=custom_components/hotel_ax --cov-report=html

# Run specific test
pytest tests/test_coordinator.py::test_handle_state_change_numeric_sensor -v
```

## Test Coverage

The test suite covers:

### Config Flow (`test_config_flow.py`)
- ✅ Initial form display
- ✅ Standard region selection
- ✅ Custom region with domain validation
- ✅ Domain validation (rejects http://, https://, slashes)
- ✅ Dataset configuration with connection validation
- ✅ Error handling (invalid auth, invalid dataset, connection errors)
- ✅ Duplicate entry prevention
- ✅ Full end-to-end flow (user → custom domain → datasets)

### Options Flow (`test_options_flow.py`)
- ✅ Form pre-population with existing values
- ✅ Flush interval updates
- ✅ Exclude pattern updates
- ✅ Custom domain validation when region is custom
- ✅ Whitespace handling
- ✅ API token changes
- ✅ Dataset name changes
- ✅ Min/max flush interval enforcement

### Coordinator (`test_coordinator.py`)
- ✅ Initialization with standard and custom domains
- ✅ Start/stop lifecycle
- ✅ Numeric sensor → metric recording
- ✅ Non-numeric state → log recording
- ✅ Unavailable/unknown/empty state filtering
- ✅ Exclusion pattern matching (glob patterns)
- ✅ Gauge caching and reuse
- ✅ Cache cleanup (removes stale entities)
- ✅ Flush operations
- ✅ Error handling
- ✅ Full integration with Home Assistant event bus

### Integration Lifecycle (`test_init.py`)
- ✅ Setup creates coordinator
- ✅ Setup starts coordinator
- ✅ Setup registers update listener
- ✅ Unload stops coordinator
- ✅ Reload triggers re-initialization
- ✅ Multiple setup/unload cycles
- ✅ Error handling for invalid configs

## Fixtures

Defined in `conftest.py`:

- `mock_config_entry` - Standard US East 1 config
- `mock_custom_domain_entry` - Custom domain config with exclusions
- `mock_otel_providers` - Mocked OpenTelemetry providers
- `mock_aiohttp_session` - Mocked HTTP session for validation

## CI/CD

Tests run automatically on GitHub Actions:
- On every push to main/master
- On every pull request
- For Python 3.11 and 3.12
- With coverage reporting to Codecov

See `.github/workflows/ci.yml`
