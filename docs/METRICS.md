# Prometheus Metrics Documentation

This document describes the Prometheus metrics exposed by the moderator application and how to use them for monitoring and alerting.

## Table of Contents

1. [Overview](#overview)
2. [Configuration](#configuration)
3. [Available Metrics](#available-metrics)
4. [Prometheus Setup](#prometheus-setup)
5. [Grafana Dashboards](#grafana-dashboards)
6. [Example Queries](#example-queries)
7. [Alerting Rules](#alerting-rules)

## Overview

The moderator application exposes Prometheus metrics via HTTP endpoint at `/metrics`. These metrics provide insights into:

- Message processing throughput
- Task creation and status distribution
- Reply delivery rates
- LLM API usage and performance
- Error rates by type
- Response times for various operations
- Current system state (open tasks, allowlist size)

## Configuration

### Environment Variables

Add the following to your `.env` file to enable metrics:

```bash
# Enable Prometheus metrics endpoint
METRICS_ENABLED=true

# Metrics server port (default: same as HEALTH_CHECK_PORT)
METRICS_PORT=8000

# Gauge metrics update interval in seconds (default: 60)
METRICS_UPDATE_INTERVAL=60
```

### Security Considerations

**IMPORTANT**: The metrics endpoint is disabled by default for security reasons.

When enabled, the `/metrics` endpoint exposes operational data that could be useful to attackers. To secure it:

1. **Network isolation**: Only allow access from trusted networks (Prometheus server)
2. **Firewall rules**: Restrict access to the metrics port
3. **Authentication**: Use a reverse proxy with authentication if exposing publicly
4. **TLS**: Enable HTTPS for the metrics endpoint in production

Example Nginx configuration with authentication:

```nginx
location /metrics {
    auth_basic "Metrics";
    auth_basic_user_file /etc/nginx/.htpasswd;
    proxy_pass http://backend:8000/metrics;
}
```

## Available Metrics

### Counter Metrics

Counter metrics only increase over time (or reset to zero on restart).

#### `messages_total`

Total number of messages processed by platform.

**Labels:**
- `platform`: Platform name (`discord`, `telegram`)

**Example:**
```
messages_total{platform="discord"} 1234
messages_total{platform="telegram"} 567
```

#### `tasks_total`

Total number of tasks created by status.

**Labels:**
- `status`: Task status (`pending`, `approved`, `rejected`, `muted`, `error`)

**Example:**
```
tasks_total{status="pending"} 89
tasks_total{status="approved"} 234
tasks_total{status="rejected"} 45
```

#### `replies_total`

Total number of replies sent by platform.

**Labels:**
- `platform`: Platform name (`discord`, `telegram`)

**Example:**
```
replies_total{platform="discord"} 890
replies_total{platform="telegram"} 12
```

#### `llm_requests_total`

Total number of LLM API requests by provider and status.

**Labels:**
- `provider`: LLM provider (`openai`, `anthropic`)
- `status`: Request status (`success`, `error`)

**Example:**
```
llm_requests_total{provider="openai",status="success"} 456
llm_requests_total{provider="openai",status="error"} 12
```

#### `errors_total`

Total number of errors encountered by type.

**Labels:**
- `error_type`: Error category (`database`, `discord`, `telegram`, `llm`, `validation`, `unknown`)

**Example:**
```
errors_total{error_type="database"} 5
errors_total{error_type="discord"} 12
errors_total{error_type="llm"} 3
```

### Histogram Metrics

Histogram metrics track the distribution of values over time.

#### `response_time_seconds`

Response time distribution in seconds for various operations.

**Labels:**
- `operation`: Operation type (`message_processing`, `llm_request`, `database_query`)

**Buckets:** 0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0, 120.0, 300.0, 600.0, 1800.0 seconds

**Example:**
```
response_time_seconds_bucket{operation="message_processing",le="1.0"} 234
response_time_seconds_bucket{operation="message_processing",le="5.0"} 567
response_time_seconds_sum{operation="message_processing"} 1234.5
response_time_seconds_count{operation="message_processing"} 600
```

### Gauge Metrics

Gauge metrics represent current state and can increase or decrease.

#### `open_tasks_count`

Current number of open (pending) tasks.

**Example:**
```
open_tasks_count 42
```

#### `allowlist_size`

Current number of channels in the allowlist by platform.

**Labels:**
- `platform`: Platform name (`discord`, `telegram`)

**Example:**
```
allowlist_size{platform="discord"} 15
allowlist_size{platform="telegram"} 3
```

#### `app_info`

Application metadata (always set to 1).

**Labels:**
- `version`: Application version
- `environment`: Environment name (`production`, `development`)

**Example:**
```
app_info{version="1.0.0",environment="production"} 1
```

## Prometheus Setup

### 1. Install Prometheus

#### Using Docker Compose

Add to your `docker-compose.yml`:

```yaml
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./prometheus.yml:/etc/prometheus/prometheus.yml
      - prometheus_data:/prometheus
    command:
      - '--config.file=/etc/prometheus/prometheus.yml'
      - '--storage.tsdb.path=/prometheus'
    networks:
      - moderator-network

volumes:
  prometheus_data:
```

#### Standalone Installation

```bash
# Download and extract
wget https://github.com/prometheus/prometheus/releases/download/v2.45.0/prometheus-2.45.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
cd prometheus-*

# Run with configuration
./prometheus --config.file=prometheus.yml
```

### 2. Configure Scraping

Create or update `prometheus.yml` using the example in `docs/prometheus-config.yml`.

### 3. Verify Collection

1. Start Prometheus: `docker-compose up -d prometheus`
2. Open Prometheus UI: http://localhost:9090
3. Go to Status > Targets
4. Verify moderator target is "UP"
5. Run test query: `messages_total`

## Grafana Dashboards

### Sample Dashboard Panels

#### Message Processing Rate

```promql
rate(messages_total[5m])
```

#### Task Completion Rate

```promql
rate(tasks_total{status="approved"}[5m])
```

#### Error Rate

```promql
rate(errors_total[5m])
```

#### P95 Response Time

```promql
histogram_quantile(0.95, rate(response_time_seconds_bucket[5m]))
```

#### LLM Success Rate

```promql
rate(llm_requests_total{status="success"}[5m]) / rate(llm_requests_total[5m])
```

## Example Queries

### Messages per Platform (Last Hour)

```promql
increase(messages_total[1h])
```

### Average Response Time by Operation

```promql
rate(response_time_seconds_sum[5m]) / rate(response_time_seconds_count[5m])
```

### Current Open Tasks

```promql
open_tasks_count
```

### LLM Error Rate

```promql
rate(llm_requests_total{status="error"}[5m]) / rate(llm_requests_total[5m]) * 100
```

### Top Error Types

```promql
topk(5, rate(errors_total[1h]))
```

## Alerting Rules

Create `/etc/prometheus/rules/moderator.yml`:

```yaml
groups:
  - name: moderator_alerts
    interval: 30s
    rules:
      # High error rate
      - alert: HighErrorRate
        expr: rate(errors_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High error rate detected"
          description: "Error rate is {{ $value }} errors/sec"

      # Too many open tasks
      - alert: TooManyOpenTasks
        expr: open_tasks_count > 100
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Too many open tasks"
          description: "{{ $value }} tasks are pending"

      # LLM error rate high
      - alert: HighLLMErrorRate
        expr: rate(llm_requests_total{status="error"}[5m]) / rate(llm_requests_total[5m]) > 0.1
        for: 5m
        labels:
          severity: critical
        annotations:
          summary: "High LLM error rate"
          description: "LLM error rate is {{ $value | humanizePercentage }}"

      # Slow response times
      - alert: SlowResponseTime
        expr: histogram_quantile(0.95, rate(response_time_seconds_bucket[5m])) > 30
        for: 10m
        labels:
          severity: warning
        annotations:
          summary: "Slow response times"
          description: "P95 response time is {{ $value }}s"

      # Application down
      - alert: ApplicationDown
        expr: up{job="moderator"} == 0
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Application is down"
          description: "Moderator application cannot be scraped"
```

Add to `prometheus.yml`:

```yaml
rule_files:
  - '/etc/prometheus/rules/*.yml'
```

## Testing Metrics

### Manual Testing

```bash
# Enable metrics in .env
echo "METRICS_ENABLED=true" >> .env

# Restart application
docker-compose restart backend

# Test endpoint
curl http://localhost:8000/metrics

# Expected output: Prometheus-formatted metrics
```

### Automated Testing

```bash
# Run metrics tests
cd tests
python -m pytest test_metrics.py -v
```

## Performance Considerations

- **Scrape Interval**: Default 30s. Adjust based on needs vs load.
- **Retention**: Prometheus stores data for 15 days by default.
- **Cardinality**: Avoid high-cardinality labels (e.g., user IDs, message IDs).
- **Resource Usage**: Metrics add minimal overhead (~1-2% CPU, ~10MB memory).

## Troubleshooting

### Metrics endpoint returns 404

- Check `METRICS_ENABLED=true` in `.env`
- Verify application restarted after config change
- Check logs for metrics initialization message

### No data in Prometheus

- Verify Prometheus can reach the application
- Check Prometheus targets page for errors
- Verify firewall rules allow scraping
- Check application logs for errors

### Incorrect metric values

- Counters reset on application restart
- Gauge updates occur every 60s by default
- Verify database connectivity for gauge metrics

## Additional Resources

- [Prometheus Documentation](https://prometheus.io/docs/)
- [Prometheus Best Practices](https://prometheus.io/docs/practices/naming/)
- [Grafana Documentation](https://grafana.com/docs/)
- [PromQL Tutorial](https://prometheus.io/docs/prometheus/latest/querying/basics/)
