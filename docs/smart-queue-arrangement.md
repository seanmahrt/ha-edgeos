# Smart Queue Sensor and Switch Arrangement

## Goal

Provide Smart Queue visibility in Home Assistant with minimal router and HA load, while keeping entities organized and easy to understand.

## Device Placement

Smart Queue entities are grouped under the existing system device for now.

- Device: Router System device
- Rationale: simplest implementation and lowest migration risk

## Naming Layout

Smart Queue entities are policy-prefixed for better organization.

- Pattern: `<Router Name> <Entity Label> [<Policy>]`
- Example: `LAS-MLI Smart Queue Upload Limit [Tmo]`

If multiple policies are detected and a single-entity name cannot be tied to one policy:

- Pattern fallback: `<Router Name> <Entity Label> [MultiPolicy]`

## Switch Arrangement

A dedicated Smart Queue monitor switch is used to gate high-churn runtime metrics.

- Switch: `Smart Queue Monitored`
- Scope: system-level
- Purpose: turn runtime Smart Queue telemetry on/off without changing other interface/device monitoring

This switch should control only Smart Queue runtime sensors and not affect:

- Interface monitored switches
- Device monitored switches
- Core system sensors

## Sensor Arrangement

### Always-On Configuration/Metadata Sensors

These are low-churn and should remain available regardless of Smart Queue monitor switch state.

- `smart_queue_total`
- `smart_queue_enabled`
- `smart_queue_interfaces`
- `smart_queue_upload_limit`
- `smart_queue_download_limit`

### Runtime/WebSocket Sensors (Gated by Smart Queue Monitor Switch)

These can update frequently and should be disabled when the Smart Queue monitor switch is off.

- `smart_queue_rx_rate`
- `smart_queue_tx_rate`
- `smart_queue_rx_traffic`
- `smart_queue_tx_traffic`
- `smart_queue_rx_dropped`
- `smart_queue_tx_dropped`
- `smart_queue_rx_errors`
- `smart_queue_tx_errors`
- `smart_queue_rx_packets`
- `smart_queue_tx_packets`

When the Smart Queue monitor switch is off:

- Runtime sensors should report unavailable (`None`) instead of stale values.

## Attributes on Smart Queue Summary

The Smart Queue summary sensor should expose organization and diagnostics attributes.

- `advanced_settings`
- `advanced_settings_count`
- `policy_map` (policy name and wan interface)
- `wan_interfaces`
- `direction_states`
- `upload_configured`
- `upload_enabled`
- `upload_disabled`
- `download_configured`
- `download_enabled`
- `download_disabled`
- `monitored`

## Data and Unit Expectations

Smart Queue policy rates from EdgeOS are bit-based (for example `12mbit`).

- Integration normalization: convert to bytes/sec before publishing to HA data-rate sensors.
- Reason: HA data-rate units in this integration are byte-based.

## Load and Robustness Rules

- No additional REST polling for Smart Queue beyond existing refresh cycle.
- Reuse existing websocket flow for runtime counters.
- Use monitor switch gating to reduce recorder/state churn.
- Avoid per-policy websocket assumptions unless mapping is explicitly reliable.

## Future Option (Optional)

If entity volume grows further, Smart Queue can be moved to a separate device class later.

- Current recommendation: keep on system device plus dedicated Smart Queue monitor switch for simplicity.
