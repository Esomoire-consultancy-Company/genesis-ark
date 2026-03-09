# Telemetry

The telemetry module implements **RiverOS** — the telemetry and observability backbone of Genesis Ark.

All platform components emit structured events and metrics to RiverOS, enabling real-time operational visibility, alerting, and telemetry-driven workflow automation.

## Contents

| File / Folder | Description |
|---|---|
| `prometheus.yml` | Prometheus scrape configuration |
| `pipelines/` | Event pipeline definitions |
| `dashboards/` | Grafana dashboard JSON exports |
| `alerts/` | Alert rules and notification configs |
| `schemas/` | Event schema definitions (CloudEvents) |

## Prometheus Configuration

The default `prometheus.yml` scrapes all Genesis Ark core services. Add new scrape targets for additional modules.

## Event Schema

All platform events follow the [CloudEvents](https://cloudevents.io/) specification:

```json
{
  "specversion": "1.0",
  "type": "com.genesis-ark.<component>.<event>",
  "source": "https://genesis-ark/<component>",
  "id": "<uuid>",
  "time": "ISO-8601",
  "datacontenttype": "application/json",
  "data": {}
}
```

## Integration

- All modules in this repository emit events to RiverOS.
- SynergizeOS consumes telemetry events for operational planning.
- Alerts route to governance when policy thresholds are breached.
