# ShopMindAI API Documentation

Complete API reference for the ShopMindAI diagnostic assistant.

**Base URL**: `http://localhost:8000` (local) or `https://your-domain.com` (production)

---

## Table of Contents

- [Security](#security)
- [Authentication](#authentication)
- [Rate Limiting](#rate-limiting)
- [Error Handling](#error-handling)
- [Endpoints](#endpoints)
  - [POST /api/diagnose](#post-apidiagnose)
  - [GET /health](#get-health)
- [Request Examples](#request-examples)
- [Response Codes](#response-codes)
- [Client Libraries](#client-libraries)

---

## Security

### SQL Injection Protection

All database queries use **SQLAlchemy ORM**, which automatically parameterizes all queries:

- ✅ **All queries are parameterized**: User input is bound as parameters, never interpolated into SQL strings
- ✅ **Input validation**: All request parameters are validated via Pydantic before database use
- ✅ **Defense in depth**: Safe query utilities in `app/query_utils.py` provide additional validation layers

**Protected fields**:
- Session IDs: Validated as positive integers before query
- Booleans (training_ready): ORM-filtered, safe from injection
- Text fields (symptoms, confirmed_cause): Parameterized by SQLAlchemy

**Development approach**:
- Never use f-strings or `.format()` with user input in queries
- Use column filters: `Model.id == session_id` (parameterized)
- Use safe validators: `validate_int_id()`, `validate_non_empty_string()` from `query_utils.py`

For detailed implementation, see `app/database.py` and `app/query_utils.py`.

---

## Authentication

**Current Version**: No authentication required (internal shop use only)

For future versions with authentication:
- API Key in header: `X-API-Key: your-api-key`
- Bearer token: `Authorization: Bearer your-token`

---

## Rate Limiting

Requests are rate-limited per IP address using a token bucket algorithm:

| Endpoint | Limit | Window |
|----------|-------|--------|
| `POST /api/diagnose` | 10 requests | per minute |
| `GET /health` | 100 requests | per minute |

**Rate Limit Headers** (included in response):
```
X-RateLimit-Limit: 10
X-RateLimit-Remaining: 7
X-RateLimit-Reset: 1708459200
```

**Rate Limit Exceeded Response**:
```json
{
  "detail": "Rate limit exceeded: 10 per 1 minute"
}
```
**Status Code**: `429 Too Many Requests`

---

## Error Handling

All errors return JSON with the following structure:

```json
{
  "detail": "Error message describing what went wrong",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

### Error Categories

| Status Code | Meaning | Common Causes |
|-------------|---------|---------------|
| `400 Bad Request` | Invalid request format | Malformed JSON, missing fields |
| `422 Unprocessable Entity` | Validation error | Invalid VIN/OBD format, symptoms too short/long |
| `429 Too Many Requests` | Rate limit exceeded | Too many requests from your IP |
| `500 Internal Server Error` | Server processing error | Model failure, retrieval error, system issue |
| `503 Service Unavailable` | Service temporarily down | Maintenance mode, model loading |

---

## Endpoints

### POST /api/diagnose

Analyze vehicle diagnostics and return ranked diagnostic causes.

**Rate Limit**: 10 requests/minute

#### Request

**URL**: `/api/diagnose`  
**Method**: `POST`  
**Content-Type**: `application/json`

**Body Schema**:
```json
{
  "vin": "string (17 characters, alphanumeric, ISO 3779)",
  "obd_codes": ["array of strings (format: P/B/C/U + 4 digits)"],
  "symptoms": "string (10-5000 characters)",
  "max_results": "integer (optional, 1-10, default: 5)"
}
```

**Field Validation**:

| Field | Required | Format | Notes |
|-------|----------|--------|-------|
| `vin` | Yes | Exactly 17 alphanumeric chars | ISO 3779 format |
| `obd_codes` | Yes | `[P\|B\|C\|U][0-9]{4}` | Example: `P0420`, `U0100` |
| `symptoms` | Yes | 10-5000 characters | Customer-reported issues |
| `max_results` | No | Integer 1-10 | Default: 5 diagnostic results |

**Example Request**:
```json
{
  "vin": "1HGBH41JXMN109186",
  "obd_codes": ["P0420", "P0171"],
  "symptoms": "Check engine light is on. Car has rough idle and poor fuel economy. Engine occasionally misfires at idle.",
  "max_results": 5
}
```

#### Response

**Status Code**: `200 OK`

**Body Schema**:
```json
{
  "request_id": "uuid",
  "vin": "string",
  "vehicle_info": {
    "make": "string",
    "model": "string",
    "year": "string"
  },
  "diagnostics": [
    {
      "rank": "integer (1-based)",
      "cause": "string",
      "confidence": "float (0.0-1.0)",
      "explanation": "string",
      "supporting_docs": [
        {
          "source": "string (filename)",
          "page": "integer",
          "relevance": "float (0.0-1.0)"
        }
      ],
      "suggested_tests": ["array of strings"]
    }
  ],
  "processing_time_ms": "integer"
}
```

**Example Response**:
```json
{
  "request_id": "550e8400-e29b-41d4-a716-446655440000",
  "vin": "1HGBH41JXMN109186",
  "vehicle_info": {
    "make": "Honda",
    "model": "Accord",
    "year": "2021"
  },
  "diagnostics": [
    {
      "rank": 1,
      "cause": "Catalytic converter efficiency below threshold",
      "confidence": 0.87,
      "explanation": "P0420 indicates the catalytic converter is not operating efficiently. This is often caused by a worn catalyst, but can also be due to O2 sensor issues. P0171 (system too lean) may contribute to catalyst damage. Rough idle and poor fuel economy are consistent with a failing catalyst.",
      "supporting_docs": [
        {
          "source": "Honda_Accord_2021_Service_Manual.pdf",
          "page": 142,
          "relevance": 0.91
        },
        {
          "source": "Honda_P0420_Diagnostic_Guide.pdf",
          "page": 3,
          "relevance": 0.89
        }
      ],
      "suggested_tests": [
        "Measure O2 sensor voltage upstream and downstream",
        "Check exhaust backpressure",
        "Verify fuel trim values at idle and cruise",
        "Inspect catalyst for physical damage or contamination"
      ]
    },
    {
      "rank": 2,
      "cause": "Vacuum leak causing lean condition and rough idle",
      "confidence": 0.76,
      "explanation": "P0171 directly indicates a lean fuel condition. A vacuum leak can cause both rough idle and trigger P0171. The P0420 may be a secondary effect of prolonged lean running.",
      "supporting_docs": [
        {
          "source": "Honda_Accord_2021_Service_Manual.pdf",
          "page": 89,
          "relevance": 0.84
        }
      ],
      "suggested_tests": [
        "Smoke test for vacuum leaks",
        "Inspect intake manifold gaskets",
        "Check brake booster hose",
        "Verify PCV valve operation"
      ]
    }
  ],
  "processing_time_ms": 1247
}
```

#### Error Responses

**422 Unprocessable Entity** - Invalid input:
```json
{
  "detail": [
    {
      "loc": ["body", "vin"],
      "msg": "VIN must be exactly 17 alphanumeric characters",
      "type": "value_error"
    }
  ]
}
```

**500 Internal Server Error** - Processing failure:
```json
{
  "detail": "Failed to retrieve relevant documents from vector store",
  "request_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

### GET /health

Check application health and component status.

**Rate Limit**: 100 requests/minute

#### Request

**URL**: `/health`  
**Method**: `GET`  
**Content-Type**: N/A (no body)

#### Response

**Status Code**: `200 OK`

**Body Schema**:
```json
{
  "status": "healthy | degraded | unhealthy",
  "timestamp": "ISO 8601 timestamp with timezone",
  "version": "string",
  "components": {
    "embedding_model": "loaded | loading | error",
    "vector_store": "ready | loading | error",
    "llm_provider": "gcp_connected | siliconeflow_connected | error"
  }
}
```

**Example Response**:
```json
{
  "status": "healthy",
  "timestamp": "2026-02-20T10:30:45.123456-08:00",
  "version": "1.0.0",
  "components": {
    "embedding_model": "loaded",
    "vector_store": "ready",
    "llm_provider": "gcp_connected"
  }
}
```

**Unhealthy Response**:
```json
{
  "status": "unhealthy",
  "timestamp": "2026-02-20T10:30:45.123456-08:00",
  "version": "1.0.0",
  "components": {
    "embedding_model": "loaded",
    "vector_store": "ready",
    "llm_provider": "error: connection timeout"
  }
}
```

---

## Request Examples

### cURL

**Diagnostic Analysis**:
```bash
curl -X POST http://localhost:8000/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "vin": "1HGBH41JXMN109186",
    "obd_codes": ["P0420", "P0171"],
    "symptoms": "Check engine light on, rough idle, poor fuel economy",
    "max_results": 3
  }'
```

**Health Check**:
```bash
curl http://localhost:8000/health
```

### Python (requests)

```python
import requests

# Diagnostic Analysis
url = "http://localhost:8000/api/diagnose"
payload = {
    "vin": "1HGBH41JXMN109186",
    "obd_codes": ["P0420", "P0171"],
    "symptoms": "Check engine light on, rough idle, poor fuel economy",
    "max_results": 3
}

response = requests.post(url, json=payload)

if response.status_code == 200:
    data = response.json()
    print(f"Request ID: {data['request_id']}")
    print(f"Vehicle: {data['vehicle_info']['year']} {data['vehicle_info']['make']} {data['vehicle_info']['model']}")
    print(f"\nTop {len(data['diagnostics'])} Diagnostics:")
    for diag in data['diagnostics']:
        print(f"\n{diag['rank']}. {diag['cause']}")
        print(f"   Confidence: {diag['confidence']:.2%}")
        print(f"   {diag['explanation']}")
else:
    print(f"Error: {response.status_code}")
    print(response.json())

# Health Check
health_response = requests.get("http://localhost:8000/health")
print(health_response.json())
```

### JavaScript (fetch)

```javascript
// Diagnostic Analysis
const diagnose = async () => {
  const response = await fetch('http://localhost:8000/api/diagnose', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({
      vin: '1HGBH41JXMN109186',
      obd_codes: ['P0420', 'P0171'],
      symptoms: 'Check engine light on, rough idle, poor fuel economy',
      max_results: 3
    })
  });

  if (response.ok) {
    const data = await response.json();
    console.log('Request ID:', data.request_id);
    console.log('Vehicle:', `${data.vehicle_info.year} ${data.vehicle_info.make} ${data.vehicle_info.model}`);
    console.log('Diagnostics:', data.diagnostics);
  } else {
    console.error('Error:', response.status, await response.json());
  }
};

// Health Check
const checkHealth = async () => {
  const response = await fetch('http://localhost:8000/health');
  const health = await response.json();
  console.log('Health Status:', health);
};

diagnose();
checkHealth();
```

---

## Response Codes

| Code | Status | Description |
|------|--------|-------------|
| `200` | OK | Request successful |
| `400` | Bad Request | Malformed request (invalid JSON) |
| `422` | Unprocessable Entity | Validation error (invalid VIN, OBD codes, etc.) |
| `429` | Too Many Requests | Rate limit exceeded |
| `500` | Internal Server Error | Server processing error |
| `503` | Service Unavailable | Service temporarily down |

---

## Client Libraries

### Python Client

**Installation**:
```bash
pip install requests
```

**Usage**:
```python
from shopmind_client import ShopMindClient

client = ShopMindClient(base_url="http://localhost:8000")

# Run diagnostic
result = client.diagnose(
    vin="1HGBH41JXMN109186",
    obd_codes=["P0420", "P0171"],
    symptoms="Check engine light on, rough idle, poor fuel economy"
)

print(f"Top cause: {result.diagnostics[0].cause}")
print(f"Confidence: {result.diagnostics[0].confidence:.2%}")
```

### JavaScript/TypeScript Client

**Installation**:
```bash
npm install shopmind-client
```

**Usage**:
```typescript
import { ShopMindClient } from 'shopmind-client';

const client = new ShopMindClient('http://localhost:8000');

const result = await client.diagnose({
  vin: '1HGBH41JXMN109186',
  obd_codes: ['P0420', 'P0171'],
  symptoms: 'Check engine light on, rough idle, poor fuel economy',
  max_results: 5
});

console.log(`Top cause: ${result.diagnostics[0].cause}`);
console.log(`Confidence: ${(result.diagnostics[0].confidence * 100).toFixed(1)}%`);
```

---

## Interactive Documentation

FastAPI provides automatic interactive API documentation:

- **Swagger UI**: http://localhost:8000/docs
- **ReDoc**: http://localhost:8000/redoc

These interfaces allow you to:
- View all endpoints and schemas
- Test API calls directly in the browser
- Download OpenAPI spec (JSON/YAML)

---

## API Changelog

### v1.0.0 (2026-02-20)
- Initial production release
- POST /api/diagnose endpoint
- GET /health endpoint
- Rate limiting implementation
- Input validation with Pydantic

### Upcoming (v1.1.0)
- VIN decoding via NHTSA API
- Diagnostic history tracking
- Export diagnostics to PDF
- WebSocket support for real-time updates

---

## Support

- **Documentation**: [README.md](README.md)
- **Issues**: https://github.com/yourusername/shopmindai/issues
- **Email**: support@shopmindai.com

---

**Built with ❤️ for automotive mechanics**
