# ShopMindAI Deployment Guide

Complete guide for deploying ShopMindAI to production on Google Cloud Platform.

---

## Table of Contents

- [Prerequisites](#prerequisites)
- [Local Development Setup](#local-development-setup)
- [GCP VM Deployment](#gcp-vm-deployment)
- [Docker Deployment](#docker-deployment)
- [Reverse Proxy Setup (nginx)](#reverse-proxy-setup-nginx)
- [SSL/TLS Configuration](#ssltls-configuration)
- [Monitoring & Health Checks](#monitoring--health-checks)
- [Backup & Recovery](#backup--recovery)
- [Troubleshooting](#troubleshooting)
- [Maintenance](#maintenance)

---

## Prerequisites

### Required
- **GCP Account** with billing enabled
- **Domain Name** (optional, for SSL/custom URL)
- **SSH Key** for GCP VM access
- **Git** installed locally
- **Docker** and **Docker Compose** (for local testing)

### Recommended
- **gcloud CLI** installed and configured
- **Postman** or **curl** for API testing
- **GCP Project** dedicated to ShopMindAI

---

## Local Development Setup

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/shopmindai.git
cd shopmindai
```

### 2. Create Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

### 4. Configure Environment

```bash
cp .env.example .env
nano .env  # Edit with your settings
```

**Minimum configuration for local dev**:
```bash
DEFAULT_PROVIDER=gcp
GCP_MODEL_URL=http://localhost:9000/generate
ALLOWED_ORIGINS=*
LOG_LEVEL=DEBUG
FAISS_INDEX_PATH=data/faiss_index
MAX_RETRIEVE_DOCS=10
```

### 5. Run Locally

```bash
python3 -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 6. Test Locally

```bash
# Health check
curl http://localhost:8000/health

# Test diagnostic (replace with valid data)
curl -X POST http://localhost:8000/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "vin": "1HGBH41JXMN109186",
    "obd_codes": ["P0420"],
    "symptoms": "Check engine light on"
  }'
```

---

## GCP VM Deployment

### Step 1: Provision VM

#### Using gcloud CLI

```bash
# Set project
gcloud config set project YOUR_PROJECT_ID

# Create VM
gcloud compute instances create shopmindai-vm \
  --zone=us-central1-a \
  --machine-type=n1-standard-2 \
  --image-family=ubuntu-2204-lts \
  --image-project=ubuntu-os-cloud \
  --boot-disk-size=50GB \
  --boot-disk-type=pd-standard \
  --tags=http-server,https-server \
  --metadata=startup-script='#!/bin/bash
    apt-get update
    apt-get install -y docker.io docker-compose git
    systemctl enable docker
    systemctl start docker
    usermod -aG docker $(whoami)
  '
```

#### Using GCP Console

1. Navigate to **Compute Engine** > **VM instances**
2. Click **CREATE INSTANCE**
3. Configure:
   - **Name**: `shopmindai-vm`
   - **Region**: `us-central1` (or your preferred region)
   - **Zone**: `us-central1-a`
   - **Machine type**: `n1-standard-2` (2 vCPUs, 7.5 GB RAM)
   - **Boot disk**: Ubuntu 22.04 LTS, 50 GB
   - **Firewall**: Allow HTTP and HTTPS traffic
4. Click **CREATE**

### Step 2: Reserve Static IP

```bash
# Create static IP
gcloud compute addresses create shopmindai-ip \
  --region=us-central1

# Get the IP address
gcloud compute addresses describe shopmindai-ip \
  --region=us-central1 \
  --format="get(address)"

# Attach to VM
gcloud compute instances delete-access-config shopmindai-vm \
  --access-config-name="External NAT" \
  --zone=us-central1-a

gcloud compute instances add-access-config shopmindai-vm \
  --access-config-name="External NAT" \
  --address=shopmindai-ip \
  --zone=us-central1-a
```

### Step 3: Configure Firewall

```bash
# Allow HTTP (port 80)
gcloud compute firewall-rules create allow-http \
  --allow=tcp:80 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=http-server

# Allow HTTPS (port 443)
gcloud compute firewall-rules create allow-https \
  --allow=tcp:443 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=https-server

# Allow SSH (port 22) - usually already enabled
gcloud compute firewall-rules create allow-ssh \
  --allow=tcp:22 \
  --source-ranges=0.0.0.0/0 \
  --target-tags=ssh
```

### Step 4: SSH into VM

```bash
gcloud compute ssh shopmindai-vm --zone=us-central1-a
```

### Step 5: Install Docker on VM

```bash
# Update packages
sudo apt-get update

# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh

# Add user to docker group
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Verify installation
docker --version
docker-compose --version

# Log out and back in for group changes to take effect
exit
gcloud compute ssh shopmindai-vm --zone=us-central1-a
```

---

## Docker Deployment

### Step 1: Clone Repository on VM

```bash
cd ~
git clone https://github.com/yourusername/shopmindai.git
cd shopmindai
```

### Step 2: Configure Environment

```bash
cp .env.example .env
nano .env
```

**Production configuration**:
```bash
# LLM Provider
DEFAULT_PROVIDER=gcp
GCP_MODEL_URL=http://YOUR_GCP_MODEL_IP:9000/generate
SILICONEFLOW_API_KEY=sk-your-actual-key-here
SILICONEFLOW_URL=https://api.siliconeflow.com/v1/chat

# Security - IMPORTANT: Replace with your domain(s)
ALLOWED_ORIGINS=https://yourdomain.com,https://app.yourdomain.com

# Logging
LOG_LEVEL=INFO

# Vector Store
FAISS_INDEX_PATH=data/faiss_index

# Retrieval
MAX_RETRIEVE_DOCS=10
```

**Security Notes**:
- Replace `ALLOWED_ORIGINS=*` with your actual domain(s)
- Keep `SILICONEFLOW_API_KEY` secret
- Use `chmod 600 .env` to restrict file permissions

### Step 3: Build and Run

```bash
# Build Docker image
docker-compose build

# Start services in background
docker-compose up -d

# Verify containers are running
docker-compose ps

# Check logs
docker-compose logs -f shopmind
```

### Step 4: Verify Deployment

```bash
# Health check (from VM)
curl http://localhost:8000/health

# Health check (from external)
curl http://YOUR_VM_IP:8000/health

# Test diagnostic endpoint
curl -X POST http://YOUR_VM_IP:8000/api/diagnose \
  -H "Content-Type: application/json" \
  -d '{
    "vin": "1HGBH41JXMN109186",
    "obd_codes": ["P0420"],
    "symptoms": "Check engine light on, rough idle"
  }'
```

---

## Reverse Proxy Setup (nginx)

Running ShopMindAI behind nginx provides:
- SSL/TLS termination
- Better security
- Load balancing (future)
- Request logging
- DDoS protection

### Step 1: Install nginx

```bash
sudo apt-get update
sudo apt-get install -y nginx
```

### Step 2: Configure nginx

```bash
# Create configuration file
sudo nano /etc/nginx/sites-available/shopmindai
```

**Basic HTTP configuration**:
```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;

    # Increase timeouts for LLM processing
    proxy_connect_timeout 60s;
    proxy_send_timeout 60s;
    proxy_read_timeout 60s;

    # Request size limits
    client_max_body_size 1M;

    # Logging
    access_log /var/log/nginx/shopmindai_access.log;
    error_log /var/log/nginx/shopmindai_error.log;

    # Proxy to ShopMindAI
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (future)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Health check endpoint (no auth needed)
    location /health {
        proxy_pass http://localhost:8000/health;
        access_log off;  # Don't log health checks
    }
}
```

### Step 3: Enable Site

```bash
# Enable the site
sudo ln -s /etc/nginx/sites-available/shopmindai /etc/nginx/sites-enabled/

# Remove default site (optional)
sudo rm /etc/nginx/sites-enabled/default

# Test configuration
sudo nginx -t

# Restart nginx
sudo systemctl restart nginx
sudo systemctl enable nginx
```

### Step 4: Test Reverse Proxy

```bash
# Should now work on port 80
curl http://YOUR_DOMAIN/health
curl http://YOUR_VM_IP/health
```

---

## SSL/TLS Configuration

### Using Let's Encrypt (Free SSL)

#### Step 1: Install Certbot

```bash
sudo apt-get update
sudo apt-get install -y certbot python3-certbot-nginx
```

#### Step 2: Obtain Certificate

```bash
# Make sure your domain points to your VM IP
# Then run certbot
sudo certbot --nginx -d your-domain.com -d www.your-domain.com
```

**Follow the prompts**:
1. Enter email address
2. Agree to terms
3. Choose redirect option (recommended: redirect HTTP to HTTPS)

#### Step 3: Test SSL

```bash
# Test HTTPS
curl https://your-domain.com/health

# Check SSL rating
# Visit: https://www.ssllabs.com/ssltest/
```

#### Step 4: Auto-renewal

```bash
# Test renewal
sudo certbot renew --dry-run

# Certbot automatically configures cron job for renewal
# Verify with:
sudo systemctl status certbot.timer
```

### Updated nginx Configuration (with SSL)

After running certbot, your nginx config will look like:

```nginx
server {
    listen 80;
    server_name your-domain.com www.your-domain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name your-domain.com www.your-domain.com;

    # SSL certificates (managed by Certbot)
    ssl_certificate /etc/letsencrypt/live/your-domain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/your-domain.com/privkey.pem;
    include /etc/letsencrypt/options-ssl-nginx.conf;
    ssl_dhparam /etc/letsencrypt/ssl-dhparams.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Proxy configuration
    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /health {
        proxy_pass http://localhost:8000/health;
        access_log off;
    }
}
```

---

## Monitoring & Health Checks

### Local Health Monitoring

```bash
# Create monitoring script
cat > ~/monitor_shopmindai.sh << 'EOF'
#!/bin/bash
HEALTH_URL="http://localhost:8000/health"
SLACK_WEBHOOK="https://hooks.slack.com/services/YOUR/WEBHOOK/URL"

response=$(curl -s -o /dev/null -w "%{http_code}" $HEALTH_URL)

if [ $response -ne 200 ]; then
    # Alert to Slack
    curl -X POST $SLACK_WEBHOOK \
      -H 'Content-Type: application/json' \
      -d "{\"text\":\"🚨 ShopMindAI Health Check Failed! Status: $response\"}"
    
    # Restart service
    cd ~/shopmindai
    docker-compose restart shopmind
fi
EOF

chmod +x ~/monitor_shopmindai.sh

# Add to crontab (check every 5 minutes)
(crontab -l 2>/dev/null; echo "*/5 * * * * ~/monitor_shopmindai.sh") | crontab -
```

### UptimeRobot (External Monitoring)

1. Sign up at https://uptimerobot.com (free tier available)
2. Add Monitor:
   - **Type**: HTTP(s)
   - **URL**: `https://your-domain.com/health`
   - **Interval**: 5 minutes
   - **Alert When**: Status code != 200
3. Configure alerts (email, SMS, Slack)

### GCP Cloud Monitoring

```bash
# Install monitoring agent
curl -sSO https://dl.google.com/cloudagents/add-google-cloud-ops-agent-repo.sh
sudo bash add-google-cloud-ops-agent-repo.sh --also-install

# Configure uptime check in GCP Console
# Navigate to: Monitoring > Uptime Checks > CREATE UPTIME CHECK
```

---

## Backup & Recovery

### Automated Backup Script

```bash
# Create backup directory
sudo mkdir -p /backups/shopmindai
sudo chown $USER:$USER /backups/shopmindai

# Create backup script
cat > ~/backup_shopmindai.sh << 'EOF'
#!/bin/bash
BACKUP_DIR="/backups/shopmindai"
SHOPMIND_DIR="$HOME/shopmindai"
DATE=$(date +%Y%m%d_%H%M%S)
GCS_BUCKET="gs://your-bucket-name/shopmindai-backups"

# Backup FAISS index
echo "Backing up FAISS index..."
tar -czf "$BACKUP_DIR/faiss_$DATE.tar.gz" -C "$SHOPMIND_DIR" data/faiss_index

# Backup environment config
echo "Backing up configuration..."
cp "$SHOPMIND_DIR/.env" "$BACKUP_DIR/env_$DATE.backup"

# Upload to GCS
echo "Uploading to Google Cloud Storage..."
gsutil cp "$BACKUP_DIR/faiss_$DATE.tar.gz" "$GCS_BUCKET/"
gsutil cp "$BACKUP_DIR/env_$DATE.backup" "$GCS_BUCKET/"

# Clean up local backups older than 14 days
echo "Cleaning up old backups..."
find "$BACKUP_DIR" -type f -mtime +14 -delete

echo "Backup completed: $DATE"
EOF

chmod +x ~/backup_shopmindai.sh

# Add to crontab (daily at 2 AM)
(crontab -l 2>/dev/null; echo "0 2 * * * ~/backup_shopmindai.sh >> /var/log/shopmindai_backup.log 2>&1") | crontab -
```

### Manual Backup

```bash
cd ~/shopmindai
tar -czf ~/shopmindai_backup_$(date +%Y%m%d).tar.gz \
  data/ \
  .env \
  docker-compose.yml
```

### Restore from Backup

```bash
# Stop application
cd ~/shopmindai
docker-compose down

# Restore FAISS index
tar -xzf /backups/shopmindai/faiss_YYYYMMDD_HHMMSS.tar.gz -C ~/shopmindai

# Restore config
cp /backups/shopmindai/env_YYYYMMDD_HHMMSS.backup ~/shopmindai/.env

# Restart application
docker-compose up -d

# Verify
curl http://localhost:8000/health
```

---

## Troubleshooting

### Application Won't Start

**Check logs**:
```bash
docker-compose logs shopmind
```

**Common issues**:
1. **Port 8000 already in use**:
   ```bash
   sudo lsof -i :8000
   sudo kill -9 <PID>
   ```

2. **Missing environment variables**:
   - Verify `.env` file exists
   - Check for typos in variable names

3. **Permission errors**:
   ```bash
   sudo chown -R $USER:$USER ~/shopmindai/data
   ```

### Slow Response Times

**Check resource usage**:
```bash
docker stats shopmindai
```

**Solutions**:
1. Increase VM size (more CPU/RAM)
2. Reduce `MAX_RETRIEVE_DOCS` in `.env`
3. Optimize FAISS index (reduce documents)

### Memory Issues

**Check memory**:
```bash
free -h
docker stats
```

**Add swap space**:
```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

### Can't Connect Externally

**Check firewall**:
```bash
# GCP firewall rules
gcloud compute firewall-rules list

# VM firewall (ufw)
sudo ufw status
sudo ufw allow 80
sudo ufw allow 443
```

**Check nginx**:
```bash
sudo nginx -t
sudo systemctl status nginx
sudo systemctl restart nginx
```

### Rate Limit Issues

**Increase rate limits**:
- Edit [app/main.py](app/main.py)
- Change `@limiter.limit("10/minute")` to higher value
- Rebuild Docker image: `docker-compose build`
- Restart: `docker-compose up -d`

---

## Maintenance

### Update Application

```bash
cd ~/shopmindai

# Pull latest code
git pull origin main

# Rebuild image
docker-compose build

# Restart with zero downtime
docker-compose up -d
```

### Update System Packages

```bash
# Update Ubuntu
sudo apt-get update
sudo apt-get upgrade -y
sudo apt-get autoremove -y

# Update Docker
sudo apt-get install --only-upgrade docker-ce docker-ce-cli containerd.io
```

### View Logs

```bash
# Application logs
docker-compose logs -f shopmind

# nginx logs
sudo tail -f /var/log/nginx/shopmindai_access.log
sudo tail -f /var/log/nginx/shopmindai_error.log

# System logs
sudo journalctl -u nginx -f
```

### Restart Services

```bash
# Restart ShopMindAI
docker-compose restart shopmind

# Restart nginx
sudo systemctl restart nginx

# Restart Docker daemon
sudo systemctl restart docker
```

---

## Production Checklist

Before going live, verify:

- [ ] Static IP configured and pointing to domain
- [ ] SSL/TLS certificate installed and valid
- [ ] Environment variables configured (no defaults)
- [ ] `ALLOWED_ORIGINS` set to production domains (not `*`)
- [ ] Firewall rules configured (80, 443, SSH only)
- [ ] Health checks configured (UptimeRobot or GCP Monitoring)
- [ ] Automated backups scheduled (daily)
- [ ] Log rotation configured
- [ ] Monitoring alerts set up (email/Slack)
- [ ] Rate limits tuned for expected traffic
- [ ] Resource limits set in docker-compose.yml
- [ ] Security headers enabled in nginx
- [ ] Test diagnostic end-to-end
- [ ] Document recovery procedures for team

---

## Next Steps

1. **Load Testing**: Use `locust` or `k6` to test under load
2. **CI/CD**: Set up GitHub Actions for automated deployment
3. **Scaling**: Consider GKE (Kubernetes) for multi-VM deployment
4. **Caching**: Add Redis for frequently accessed diagnostics
5. **Database**: Add PostgreSQL for job history tracking

---

## Support

- **Documentation**: [README.md](README.md)
- **API Docs**: [API.md](API.md)
- **Issues**: https://github.com/yourusername/shopmindai/issues

---

**Built with ❤️ for automotive mechanics**
