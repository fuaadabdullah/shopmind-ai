# GCP LLM Configuration Guide

This guide helps you connect ShopMindAI to an LLM running on your GCP servers.

## Quick Start

### Option 1: Vertex AI Text Bison Model (Recommended)

If using Google Cloud Vertex AI:

```bash
# 1. Install Vertex AI SDK
pip install google-cloud-aiplatform

# 2. Create a Vertex AI endpoint wrapper (see below)

# 3. Deploy to GCP VM running the wrapper

# 4. Update .env
DEFAULT_PROVIDER=gcp
GCP_MODEL_URL=http://YOUR_VM_EXTERNAL_IP:9000/generate
```

### Option 2: Custom LLM Server on GCP VM

If you have a custom LLM server already running:

```bash
# Get your VM's external IP
gcloud compute instances describe YOUR_VM_NAME \
  --zone=YOUR_ZONE \
  --format='get(networkInterfaces[0].accessConfigs[0].natIP)'

# Update .env with:
GCP_MODEL_URL=http://YOUR_VM_EXTERNAL_IP:9000/generate
DEFAULT_PROVIDER=gcp
```

---

## Detailed Setup

### For Vertex AI Users

Create a wrapper service to expose Vertex AI as an HTTP endpoint:

**File: `gcp_vertex_ai_server.py`** (deploy to GCP VM)

```python
"""
Vertex AI LLM HTTP Server Wrapper.

Exposes Vertex AI PaLM/Bison models via HTTP for ShopMindAI integration.
Deploy to GCP VM and call on port 9000.
"""
from flask import Flask, request, jsonify
from google.cloud import aiplatform
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Vertex AI
aiplatform.init(project="YOUR_PROJECT_ID", location="us-central1")

# Initialize language model
from google.cloud.aiplatform.gapic.preview import language_service_client

def get_vertex_ai_prediction(prompt: str) -> str:
    """Get prediction from Vertex AI model."""
    client = language_service_client.LanguageServiceClient(
        client_options={"api_endpoint": "us-central1-aiplatform.googleapis.com"}
    )
    
    # Or use simpler PaLMAPI if available:
    import google.ai.generativelanguage as glm
    
    client = glm.GenerativeServiceClient()
    request = glm.GenerateTextRequest(
        model="models/text-bison-001",
        prompt=glm.TextPrompt(text=prompt),
    )
    response = client.generate_text(request)
    
    if response.candidates:
        return response.candidates[0].output
    return ""


@app.route("/generate", methods=["POST"])
def generate():
    """HTTP endpoint for LLM generation."""
    try:
        data = request.json
        prompt = data.get("prompt", "")
        
        if not prompt:
            return jsonify({"error": "Missing prompt"}), 400
        
        logger.info(f"Received request with prompt length: {len(prompt)}")
        
        # Call Vertex AI
        response_text = get_vertex_ai_prediction(prompt)
        
        logger.info(f"Generated response length: {len(response_text)}")
        
        return jsonify({"response": response_text}), 200
        
    except Exception as e:
        logger.error(f"Error: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"}), 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=9000, debug=False)
```

**Deploy to GCP VM:**

```bash
# 1. SSH into VM
gcloud compute ssh YOUR_VM_NAME --zone=YOUR_ZONE

# 2. Clone/upload your app
git clone YOUR_REPO

# 3. Install dependencies
pip install flask google-cloud-aiplatform

# 4. Create systemd service for auto-start
sudo tee /etc/systemd/system/vertex-ai-server.service > /dev/null <<EOF
[Unit]
Description=Vertex AI LLM Server
After=network.target

[Service]
Type=simple
User=YOUR_USERNAME
WorkingDirectory=/path/to/app
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python gcp_vertex_ai_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

# 5. Enable and start
sudo systemctl enable vertex-ai-server
sudo systemctl start vertex-ai-server

# 6. Check status
sudo systemctl status vertex-ai-server
```

### For Custom LLM Server Users

If you already have a custom server running:

1. Ensure it's listening on `:9000` (or update the port in GCP_MODEL_URL)
2. Ensure response format matches:
   ```json
   {
     "response": "generated text here"
   }
   ```
3. Ensure it accepts POST requests with:
   ```json
   {
     "prompt": "user prompt text"
   }
   ```

---

## Configuration Steps

### 1. Update .env File

Create/update `.env` at project root:

```bash
# Copy example if needed
cp .env.example .env

# Edit with your values
nano .env
```

Set these values:

```dotenv
# ==============================================================================
# LLM Provider Configuration
# ==============================================================================
DEFAULT_PROVIDER=gcp

# GCP Model Configuration
# Replace YOUR_VM_IP with your actual GCP VM external IP
GCP_MODEL_URL=http://YOUR_VM_EXTERNAL_IP:9000/generate

# Example:
# GCP_MODEL_URL=http://35.192.123.45:9000/generate

# ==============================================================================
# Other Configuration
# ==============================================================================
ALLOWED_ORIGINS=*
LOG_LEVEL=INFO
FAISS_INDEX_PATH=data/faiss_index
MAX_RETRIEVE_DOCS=10
```

### 2. Get Your GCP VM IP Address

```bash
# Method 1: Using gcloud CLI
gcloud compute instances describe YOUR_VM_NAME \
  --zone=us-central1-a \
  --format='value(networkInterfaces[0].accessConfigs[0].natIP)'

# Method 2: Via GCP Console
# Compute Engine > VM instances > Click your VM > Find "External IP"
```

### 3. Configure Firewall (Allow Port 9000)

```bash
# Option 1: Using gcloud
gcloud compute firewall-rules create allow-llm-server \
  --allow=tcp:9000 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=llm-server

# Option 2: Apply tag to VM
gcloud compute instances add-tags YOUR_VM_NAME \
  --tags=llm-server \
  --zone=us-central1-a

# Option 3: Via GCP Console
# VPC Network > Firewall Rules > Create Rule
# - Direction: Ingress
# - Allow: TCP 9000
# - Source IPs: 0.0.0.0/0 (or your IP ranges)
```

### 4. Test Connection

```bash
# Local test (if GCP server is running)
export GCP_MODEL_URL="http://YOUR_VM_IP:9000/generate"

# Test endpoint
curl http://YOUR_VM_IP:9000/health

# Test generation
curl -X POST http://YOUR_VM_IP:9000/generate \
  -H "Content-Type: application/json" \
  -d '{"prompt": "What is 2+2?"}'

# You should see:
# {"response": "2+2 equals 4"}
```

### 5. Test with ShopMindAI

```bash
# Start the app
python -m uvicorn app.main:app --reload

# Test health endpoint
curl http://localhost:8000/health

# Test diagnostic endpoint
curl -X POST http://localhost:8000/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "vin": "1HGBH41JXMN109186",
    "obdcodes": "P0171,P0174",
    "symptoms": "rough idle, check engine light"
  }'

# Check logs for Torch integration
# You should see: "GCP request completed in XXXms"
```

---

## Environment Variables Reference

| Variable | Value | Example |
|----------|-------|---------|
| `DEFAULT_PROVIDER` | "gcp" or "siliconeflow" | "gcp" |
| `GCP_MODEL_URL` | Your GCP LLM endpoint URL | "http://35.192.1.2:9000/generate" |
| `ALLOWED_ORIGINS` | CORS allowed origins | "*" for dev, domain for prod |
| `LOG_LEVEL` | DEBUG, INFO, WARNING, ERROR | "INFO" |
| `FAISS_INDEX_PATH` | Path to FAISS index | "data/faiss_index" |
| `MAX_RETRIEVE_DOCS` | Max docs to retrieve | "10" |

---

## Troubleshooting

### Error: "Connection refused" or "Connection timeout"

```bash
# 1. Check GCP_MODEL_URL is correct
echo $GCP_MODEL_URL

# 2. Check VM is running
gcloud compute instances list

# 3. Check server process on VM
gcloud compute ssh YOUR_VM_NAME --zone=us-central1-a
ps aux | grep python  # Look for vertex-ai-server or your LLM server
curl localhost:9000/health  # From inside VM

# 4. Check firewall allows port 9000
gcloud compute firewall-rules list --filter="sourceRanges:0.0.0.0/0"

# 5. Check external IP is accessible
ping YOUR_VM_EXTERNAL_IP  # May not respond, but can try
curl -v http://YOUR_VM_EXTERNAL_IP:9000/health
```

### Error: "Invalid JSON response" or "Missing 'response' field"

Ensure your endpoint returns:
```json
{
  "response": "text generated by the model"
}
```

Not:
```json
{
  "text": "...",
  "result": "...",
  "output": "..."
}
```

### Error: "GCP_MODEL_URL not configured"

```bash
# Check .env file exists and has correct value
cat .env | grep GCP_MODEL_URL

# If missing, add it:
echo 'GCP_MODEL_URL=http://YOUR_IP:9000/generate' >> .env

# Restart app
# (The app loads .env on startup, not dynamically)
```

### Slow Response Times

- Check VM has adequate CPU (n1-standard-2 or higher recommended)
- Monitor Vertex AI quota/rate limits
- Check network latency with `ping` and `curl`
- Add latency logging in your server code

```python
import time
start = time.time()
# ... your inference code ...
duration_ms = int((time.time() - start) * 1000)
logger.info(f"Inference took {duration_ms}ms")
```

---

## Production Setup Checklist

- [ ] GCP_MODEL_URL points to production LLM server
- [ ] Firewall rules allow traffic from app VM to LLM server VM
- [ ] LLM server has health check endpoint (`/health`)
- [ ] LLM server response matches expected format
- [ ] ENV variables don't use `localhost` (won't work across VMs)
- [ ] Use static IPs to avoid endpoint changes
- [ ] Monitor response times and error rates
- [ ] Set up alerts for server downtime
- [ ] Document your endpoint URL and format
- [ ] Test failover if using multiple LLM endpoints

---

## Alternative: Host LLM on Same VM

If you want to keep everything on one VM:

```bash
# Update GCP_MODEL_URL to use localhost
GCP_MODEL_URL=http://localhost:9000/generate

# Both services (ShopMindAI + LLM server) run on same VM
# ShopMindAI: port 8000
# LLM server: port 9000
```

---

## Next Steps

1. **Verify your GCP LLM setup** - Ensure it's running and accessible
2. **Update .env** with your GCP_MODEL_URL
3. **Test connection** with curl first
4. **Start ShopMindAI** and verify it connects
5. **Monitor logs** for any connection issues

**Questions?** Check the logs:
```bash
tail -f logs/app.log | grep -i gcp
```
