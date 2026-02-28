# ✅ GCP LLM Integration Setup Complete

## What Was Created

**4 New Configuration Files:**

1. **GCP_LLM_SETUP.md** - Complete reference guide for all GCP LLM options
2. **GCP_LLM_QUICK_START.md** - Quick start (read this first!)
3. **setup_gcp_llm.py** - Interactive Python tool to configure and test
4. **setup_gcp_llm.sh** - Bash quick reference

**2 Existing Files Enhanced:**

- `app/config.py` - Already supports GCP provider
- `app/providers/gcp_local.py` - Ready to use

---

## What Your Setup Looks Like

```
Your Request
    ↓
ShopMindAI App (localhost:8000)
    ├─ Validate & decode VIN
    ├─ Semantic search (FAISS retrieval)
    ├─ Optional Torch V2 probability engine
    └─ LLM Ranking via HTTP request
         ↓
    GCP_MODEL_URL = http://YOUR_GCP_IP:9000/generate
         ↓
Your GCP LLM Server
    (Vertex AI, Custom, etc.)
         ↓
Response
    Ranked diagnostics + Explanations + Torch insights
```

---

## Quick Commands

**Get your GCP VM IP:**
```bash
gcloud compute instances describe YOUR_VM_NAME \
  --zone=us-central1-a \
  --format='value(networkInterfaces[0].accessConfigs[0].natIP)'
```

**Configure ShopMindAI (Easy):**
```bash
python setup_gcp_llm.py --interactive
```

**Or Quick:**
```bash
python setup_gcp_llm.py --ip 35.192.123.45
```

**Start the app:**
```bash
python -m uvicorn app.main:app --reload
```

**Test the endpoint:**
```bash
curl -X POST http://localhost:8000/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "vin": "1HGBH41JXMN109186",
    "obdcodes": "P0171",
    "symptoms": "rough idle"
  }'
```

**Verify everything works:**
```bash
python setup_gcp_llm.py --test
```

---

## 3 Ways to Configure

### Option 1: Interactive (Recommended)
```bash
python setup_gcp_llm.py --interactive
# Follow prompts, automatically tests connection
```

### Option 2: Quick Setup
```bash
python setup_gcp_llm.py --ip YOUR_GCP_IP
# Fast setup with auto-testing
```

### Option 3: Manual
Edit `.env`:
```
DEFAULT_PROVIDER=gcp
GCP_MODEL_URL=http://YOUR_GCP_IP:9000/generate
```

---

## What Your LLM Endpoint Needs

Your GCP LLM server must:

1. **Accept POST requests** to `/generate`
2. **Expect JSON body:** `{"prompt": "text..."}`
3. **Return JSON response:** `{"response": "text..."}`
4. **Have health check:** `GET /health` returns 200

Example:
```bash
# Health check
curl http://YOUR_GCP_IP:9000/health
# → {"status": "ok"}

# Generation
curl -X POST http://YOUR_GCP_IP:9000/generate \
  -d '{"prompt": "Hello?"}' \
  -H "Content-Type: application/json"
# → {"response": "Hello! How can I help?"}
```

---

## Architecture

**ShopMindAI Flow with GCP LLM:**

```
1. POST /api/diagnose
   ↓
2. Validate VIN (decode vehicle info)
   ↓
3. Retrieve docs (FAISS semantic search)
   ↓
4. Get Torch context (optional ML predictions)
   ↓
5. Build LLM prompt (symptoms + docs + optional Torch)
   ↓
6. Call get_provider() → GCPProvider
   ↓
7. Post to GCP_MODEL_URL (HTTP request)
   ↓
8. LLM generates ranking
   ↓
9. Return response with diagnostics
   ↓
10. Include torch_enabled metadata
```

---

## Files You May Need

**Development:**
- `.env` - Your configuration (don't commit!)
- `.env.example` - Template (commit this)

**Documentation:**
- `GCP_LLM_QUICK_START.md` - Start here
- `GCP_LLM_SETUP.md` - Detailed guide
- `DEPLOYMENT.md` - Full deployment guide
- `WEEK2_TORCH_INTEGRATION.md` - Torch V2 ML engine

**Setup Tools:**
- `setup_gcp_llm.py` - Configuration utility
- `setup_gcp_llm.sh` - Bash quick reference

---

## Next Steps

1. ✅ Find your GCP VM external IP
2. ✅ Run interactive setup: `python setup_gcp_llm.py --interactive`
3. ✅ Start app: `python -m uvicorn app.main:app --reload`
4. ✅ Test endpoint with `/api/diagnose`
5. ✅ Check logs: `tail -f logs/app.log | grep gcp`

---

## Testing Your Setup

```bash
# Status check
python setup_gcp_llm.py --status

# Full test (health + generation)
python setup_gcp_llm.py --test

# Reconfigure
python setup_gcp_llm.py --interactive
```

---

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| "Connection refused" | Check GCP_MODEL_URL, firewall, server running |
| "Invalid JSON response" | Ensure endpoint returns `{"response": "..."}` |
| "Not configured" | Run `python setup_gcp_llm.py --interactive` |
| "Slow responses" | Check GCP VM has n1-standard-2+ CPU |
| Port 9000 not accessible | Add firewall rule allowing TCP:9000 |

See `GCP_LLM_SETUP.md` § Troubleshooting for details.

---

## You're Ready! 🚀

Your ShopMindAI is now set up to use your GCP LLM server.

**To get started:**
```bash
python setup_gcp_llm.py --interactive
```

**Questions?** Check [GCP_LLM_QUICK_START.md](GCP_LLM_QUICK_START.md)
