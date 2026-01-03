#!/usr/bin/env bash
set -e

# Create worker script
sudo cat > /home/azureuser/verifier-hit.sh <<'SCRIPT'
#!/usr/bin/env bash
curl -s -X POST "https://breach-verifier-30000.azurewebsites.net/verify/breaches" >/dev/null 2>&1
SCRIPT

sudo chmod +x /home/azureuser/verifier-hit.sh

# Create cron entry
sudo cat > /etc/cron.d/verifier-hit <<'CRON'
*/2 * * * * root /home/azureuser/verifier-hit.sh
CRON

# Restart cron (Ubuntu)
sudo systemctl restart cron || true

