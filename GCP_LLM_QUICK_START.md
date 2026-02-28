# GCP LLM Integration: Quick Start Guide

**Status**: ✅ Ready to connect  
**Time to Setup**: 5-10 minutes  
**Difficulty**: Easy

---

## What You Need

Before connecting to GCP LLM, you need:

1. ✅ **GCP Account** with an LLM server running (Vertex AI, custom server, etc.)
2. ✅ **GCP VM External IP** (e.g., `35.192.123.45`)
3. ✅ **LLM Server Port** (default: `9000`)
4. ✅ **Response Format**: Ensure your LLM endpoint returns `{"response": "text"}`

---

## One-Minute Setup

### If You Know Your GCP VM IP:

```bash
# 1. Run setup script
python setup_gcp_llm.py --ip 35.192.123.45

# 2. Start the app
python -m uvicorn app.main:app --reload

# 3. Test it
curl -X POST http://localhost:8000/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "vin": "1HGBH41JXMN109186",
    "obdcodes": "P0171",
    "symptoms": "rough idle"
  }'
```

Done! ✅

---

## Step-by-Step Setup

### Step 1: Get Your GCP VM External IP

**Option A: Using gcloud CLI**
```bash
gcloud compute instances describe YOUR_VM_NAME \
  --zone=us-central1-a \
  --format='value(networkInterfaces[0].accessConfigs[0].natIP)'
```

**Option B: Using GCP Console**
- Go to **Google Cloud Console**
- **Compute Engine** → **VM instances**
- Click your VM name
- Find **External IP** in the details panel

_Copy this IP address_

### Step 2: Configure ShopMindAI

**Option A: Interactive Setup (Recommended)**
```bash
python setup_gcp_llm.py --interactive

# Follow the prompts:
# 1. Enter GCP VM External IP
# 2. Enter LLM Server Port (default 9000)
# 3. Script tests connection automatically
# 4. Saves to .env on success
```

**Option B: Quick Setup**
```bash
python setup_gcp_llm.py --ip 35.192.123.45
```

**Option C: Manual Setup**

Edit `.env`:
```dotenv
DEFAULT_PROVIDER=gcp
GCP_MODEL_URL=http://35.192.123.45:9000/generate
```

### Step 3: Verify Connection

```bash
# Check status
python setup_gcp_llm.py --status

# Run full test
python setup_gcp_llm.py --test

# Should see:
# ✓ Health check passed
# ✓ Generation successful
```

### Step 4: Start the App

```bash
# Activate virtual environment (if needed)
source .venv/bin/activate

# Start app
python -m uvicorn app.main:app --reload

# In another terminal, test it:
curl http://localhost:8000/health
```

### Step 5: Test Diagnostic Endpoint

```bash
curl -X POST http://localhost:8000/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "vin": "1HGBH41JXMN109186",
    "obdcodes": "P0171,P0174",
    "symptoms": "rough idle, check engine light"
  }'
```

You should see a diagnostic response using your GCP LLM! ✅

---

## How It Works

```
┌─ Your Request ──────────────────┐
│  POST /api/diagnose             │
│  {vin, obdcodes, symptoms}      │
└─────────────┬────────────────────┘
              │
              ▼
┌─ ShopMindAI App ────────────────┐
│  1. Validate VIN                │
│  2. Semantic search (FAISS)     │
│  3. Get Torch context (optional)│
│  4. Call LLM ranking            │
└─────────────┬────────────────────┘
              │
              ▼
┌─ GCP → Your LLM Server ─────────┐
│  GCP_MODEL_URL (via HTTP)       │
│  ↓                              │
│  POST /generate                 │
│  {prompt: "..."}                │
│  ↑                              │
│  Response: {"response": "..."}  │
└─────────────┬────────────────────┘
              │
              ▼
┌─ Response ──────────────────────┐
│  Ranked diagnostics with        │
│  explanations from LLM          │
│  + Torch insights (if enabled)  │
└─────────────────────────────────┘
```

---

## Environment Variables

If your GCP LLM is configured differently:

| Scenario | GCP_MODEL_URL | Example |
|----------|---------------|---------|
| **Custom server on same VM** | `http://localhost:9000/generate` | For dev |
| **Custom server on another VM** | `http://35.192.IP:9000/generate` | Most common |
| **Vertex AI via wrapper** | `http://35.192.IP:9000/generate` | See GCP_LLM_SETUP.md |
| **Different port** | `http://35.192.IP:8080/generate` | If using port 8080 |

---

## Troubleshooting

### ❌ "Connection refused"

```bash
# 1. Check your GCP_MODEL_URL
cat .env | grep GCP_MODEL_URL

# 2. Verify VM is running
gcloud compute instances list

# 3. Check LLM server is running (SSH to VM)
gcloud compute ssh YOUR_VM_NAME --zone=us-central1-a
ps aux | grep llm  # or your server name

# 4. Test from VM itself
curl localhost:9000/health
```

### ❌ "Invalid JSON response"

Your endpoint must return:
```json
{
  "response": "text here"
}
```

Not:
```json
{
  "text": "...",
  "output": "...",
  "result": "..."
}
```

### ❌ "GCP_MODEL_URL not configured"

```bash
# Make sure .env has the value
echo 'GCP_MODEL_URL=http://YOUR_IP:9000/generate' >> .env

# Don't use localhost across different VMs
# Use actual external IP
```

### ❌ Slow responses (>10 seconds)

- Check GCP VM has enough CPU (n1-standard-2+ recommended)
- Check network latency: `ping YOUR_GCP_IP`
- Check LLM model inference time (may be expected)
- Monitor with: `python setup_gcp_llm.py --test`

---

## Common Configurations

### Vertex AI Bison API

If using Google's Vertex AI:

```bash
# Create a wrapper service (see GCP_LLM_SETUP.md for full code)
GCP_MODEL_URL=http://YOUR_VERTEX_AI_WRAPPER_IP:9000/generate
```

### Custom Ollama Server on GCP VM

```bash
# If running Ollama locally
GCP_MODEL_URL=http://YOUR_VM_IP:11434/api/generate
```

Note: Update the response parsing if format differs.

### Self-Hosted LLaMa

```bash
GCP_MODEL_URL=http://YOUR_VM_IP:5000/generate
```

---

## Monitoring Your Setup

### View Logs

```bash
# Real-time logs from ShopMindAI
tail -f logs/app.log | grep -i gcp

# Expected output:
# INFO: Sending request to GCP model: http://35.192.1.2:9000/generate
# INFO: GCP request completed in 2345ms
```

### Check Performance

```bash
# Time a request
time curl -X POST http://localhost:8000/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{"vin":"1HGBH41JXMN109186","obdcodes":"P0171","symptoms":"rough idle"}'
```

Expect: 2-10 seconds depending on LLM model size and GCP CPU.

---

## Next Steps

1. ✅ Configure with `setup_gcp_llm.py --interactive`
2. ✅ Test with `setup_gcp_llm.py --test`
3. ✅ Start app: `python -m uvicorn app.main:app --reload`
4. ✅ Test endpoint with `/api/diagnose`
5. 📚 Read [GCP_LLM_SETUP.md](GCP_LLM_SETUP.md) for advanced options
6. 🚀 Deploy to production when ready

---

## Need Help?

### Documentation

- **Quick Setup**: This file
- **Detailed Guide**: [GCP_LLM_SETUP.md](GCP_LLM_SETUP.md)
- **API Docs**: [API.md](API.md)
- **Deployment**: [DEPLOYMENT.md](DEPLOYMENT.md)
- **Week 2 Changes**: [WEEK2_TORCH_INTEGRATION.md](WEEK2_TORCH_INTEGRATION.md)

### Test Your Setup

```bash
# Show current status
python setup_gcp_llm.py --status

# Full diagnostic test
python setup_gcp_llm.py --test

# Interactive reconfiguration
python setup_gcp_llm.py --interactive
```

### Check Logs

```bash
# All GCP-related logs
grep -i "gcp\|model\|provider" logs/app.log

# Last 20 lines
tail -20 logs/app.log
```

---

**That's it!** Your ShopMindAI is now connected to your GCP LLM server. 🚀
