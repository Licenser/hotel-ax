# Hotel-AX

> *"Here's Data!"*

![The Shining - Here's Johnny](https://media4.giphy.com/media/QSToNb4xXf51m/giphy.gif)

**Hotel-AX** is a Home Assistant custom integration that exports all your sensor data and state changes to [Axiom](https://axiom.co) using OpenTelemetry (OTLP). Think of it as checking into a hotel where all your metrics get room service.

## Features

- 📊 **Automatic metric export**: All numeric sensor states → OTLP Gauge metrics
- 📝 **Event logging**: Non-numeric state changes (lights, switches, presence, alarms) → OTLP logs
- 🌍 **Multi-region support**: US East, EU Central, or custom Axiom edge deployments
- ⚡ **Batched & efficient**: Configurable flush intervals (default 30s)
- 🎯 **Filtering**: Exclude specific entities via glob patterns
- 🔧 **Full UI configuration**: No YAML required — config flow + options flow
- 🏠 **HACS compatible**: Install directly from HACS

---

## What gets exported?

### Numeric sensors → Metrics (Gauge)

All sensors with numeric values (temperature, humidity, power, etc.) are sent as OTLP metrics:

```
metric name: homeassistant.sensor
unit:        unit_of_measurement
value:       float(state)
attributes:  entity_id, domain, device_class, friendly_name, area_id
```

### Non-numeric entities → Logs

State changes for the following domains generate log events in Axiom:

- `binary_sensor` (motion, door, window, smoke)
- `light` (on/off)
- `switch` (on/off)
- `input_boolean`
- `person` / `device_tracker` (home/away)
- `alarm_control_panel` (armed/disarmed/triggered)
- `climate` (hvac_mode changes)
- `automation` (triggered)
- All other non-numeric state changes

```
log body:    "{friendly_name} changed to {new_state}"
severity:    INFO
attributes:  entity_id, domain, old_state, new_state, friendly_name, area_id
```

---

## Installation

### Via HACS (recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations**
3. Click the **three dots menu** → **Custom repositories**
4. Add this repository:
   - URL: `https://github.com/Licenser/hotel-ax`
   - Category: `Integration`
5. Click **Download**
6. Restart Home Assistant
7. Go to **Settings** → **Devices & Services** → **Add Integration**
8. Search for **Hotel-AX**

### Manual installation

1. Download this repository
2. Copy the `custom_components/hotel_ax` folder to your Home Assistant `custom_components/` directory
3. Restart Home Assistant
4. Add the integration via **Settings** → **Devices & Services**

---

## Configuration

### Setup wizard (3 steps)

**Step 1: Credentials & Region**

- **API Token**: Your Axiom API token (get it from [axiom.co](https://app.axiom.co/settings/tokens))
- **Region**: Choose your Axiom edge deployment
  - US East 1 (AWS) — `us-east-1.aws.edge.axiom.co`
  - EU Central 1 (AWS) — `eu-central-1.aws.edge.axiom.co`
  - Custom — enter your own domain

**Step 2: Custom domain** *(only if you selected Custom)*

- Enter your custom Axiom domain (e.g., `custom.edge.axiom.co`)

**Step 3: Datasets**

- **Logs dataset**: The Axiom **Events** dataset for logs (default: `homeassistant-logs`)
- **Metrics dataset**: The Axiom **Metrics** dataset for metrics (default: `homeassistant-metrics`)

> **Important**: You must create these datasets in Axiom first. Logs/events go to an **Events** dataset, metrics go to a **Metrics** dataset.

---

## Options (reconfiguration)

After installation, reconfigure via **Settings** → **Integrations** → **Hotel-AX** → **Configure**:

- **API Token**: Update your token
- **Region / Custom Domain**: Change region
- **Datasets**: Change dataset names
- **Flush interval**: How often to batch and send data (10-300 seconds, default 30)
- **Exclude entities**: Comma-separated glob patterns (e.g., `sensor.temp_*,binary_sensor.door_*`)

---

## Requirements

- Home Assistant 2023.1 or later
- Axiom account with:
  - An **Events** dataset (for logs)
  - A **Metrics** dataset (for metrics)
  - An API token with write permissions

---

## How it works

Hotel-AX listens to all `EVENT_STATE_CHANGED` events in Home Assistant. For each state change:

1. If the state is **numeric** → recorded as an OTLP Gauge metric
2. If the state is **non-numeric** → recorded as an OTLP log event
3. Data is batched in-memory and flushed to Axiom every N seconds (configurable)
4. Uses the official OpenTelemetry Python SDK with OTLP/HTTP exporters

---

## Troubleshooting

### Logs not appearing in Axiom?

- Check that your **Logs dataset** is an **Events** type dataset in Axiom
- Verify your API token has write permissions
- Enable debug logging in Home Assistant:
  ```yaml
  logger:
    default: info
    logs:
      custom_components.hotel_ax: debug
  ```

### Metrics not appearing?

- Check that your **Metrics dataset** is a **Metrics** type dataset in Axiom
- The `/v1/metrics` endpoint only accepts protobuf (not JSON)
- Verify your flush interval isn't too long (try setting it to 10s for testing)

### Connection errors?

- Verify the region/domain is correct
- Check your network allows HTTPS outbound to `*.axiom.co`
- Test your API token using the Axiom CLI or curl

---

## Contributing

Contributions welcome! Open an issue or PR on [GitHub](https://github.com/Licenser/hotel-ax).

---

## License

MIT

---

## Etymology

**Hotel-AX** = **Ho**me Assistant + **OTEL** + **Ax**iom

*All work and no play makes Jack export all his sensor data.*
