#!/bin/bash
# Quick start guide for connecting to GCP LLM

echo "================================"
echo "ShopMindAI → GCP LLM Quick Start"
echo "================================"
echo ""

# Check if .env exists
if [ ! -f .env ]; then
    echo "📋 Creating .env from template..."
    cp .env.example .env
    echo "✓ Created .env"
fi

echo ""
echo "Quick Setup Options:"
echo ""
echo "1️⃣  Interactive Setup (Guided)"
echo "    python setup_gcp_llm.py --interactive"
echo ""
echo "2️⃣  Quick Setup with IP"
echo "    python setup_gcp_llm.py --ip YOUR_GCP_VM_IP"
echo "    Example: python setup_gcp_llm.py --ip 35.192.123.45"
echo ""
echo "3️⃣  Manual Setup"
echo "    Edit .env and set:"
echo "    DEFAULT_PROVIDER=gcp"
echo "    GCP_MODEL_URL=http://YOUR_GCP_VM_IP:9000/generate"
echo ""
echo "4️⃣  Test Your Configuration"
echo "    python setup_gcp_llm.py --test"
echo ""
echo "================================"
echo ""
echo "🔍 Need your GCP VM IP?"
echo ""
echo "   gcloud compute instances describe YOUR_VM_NAME \\"
echo "     --zone=us-central1-a \\"
echo "     --format='value(networkInterfaces[0].accessConfigs[0].natIP)'"
echo ""
echo "📖 Full Guide: See GCP_LLM_SETUP.md"
echo ""
