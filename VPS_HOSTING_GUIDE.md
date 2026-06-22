# Alpha-Automation VPS Hosting Guide

This guide walks through installing and hosting Alpha-Automation on a Hostinger KVM1 VPS. It also includes a short local test install before moving to production.

## Part 1: Test locally on your PC

1. Open a command prompt / PowerShell in the repo folder.
2. Create and activate a Python virtual environment:
   - Windows PowerShell:
     ```powershell
     python -m venv .venv
     .\.venv\Scripts\Activate.ps1
     ```
   - macOS / Linux:
     ```bash
     python -m venv .venv
     source .venv/bin/activate
     ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Start the app locally:
   ```powershell
   $env:AA_COOKIE_SECURE = '0'
   $env:AA_ALLOW_INSECURE_SECRET = '1'
   .venv\Scripts\python -m uvicorn server:app --host 127.0.0.1 --port 8000
   ```
5. Open `http://127.0.0.1:8000/admin/login` and sign in with:
   - username: `admin`
   - password: `admin123`
6. Change the admin password immediately using either the browser UI or API token route.

## Part 2: Prepare Hostinger KVM1 VPS

1. Log in to your Hostinger control panel.
2. Create or choose a KVM1 VPS instance.
3. Use the provided SSH credentials to connect from your PC.
   ```bash
   ssh root@<YOUR_VPS_IP>
   ```
4. Update the server packages:
   ```bash
   apt update && apt upgrade -y
   ```
5. Install required packages:
   ```bash
   apt install -y python3 python3-venv python3-pip git curl
   ```

## Part 3: Deploy Alpha-Automation on the VPS

1. Clone the repository to the VPS:
   ```bash
   git clone https://github.com/<YOUR_REPO>/newrepo.git
   cd newrepo
   ```
2. Create a Python virtual environment and install dependencies:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -r requirements.txt
   ```
3. Set environment variables for production:
   ```bash
   export AA_SECRET='replace-with-a-strong-secret'
   export AA_COOKIE_SECURE='1'
   export AA_AUTO_CREATE_ADMIN='1'
   export AA_ADMIN_PASSWORD='admin123'
   ```
   - Note: Use a strong secret before opening the server to the internet.
   - If you host over HTTPS, keep `AA_COOKIE_SECURE=1`.
4. Start the app with Uvicorn and keep it running:
   ```bash
   .venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8000
   ```

## Part 4: Configure a production service

For a more reliable deployment, create a systemd service file.

### Create `/etc/systemd/system/alpha-automation.service`

```ini
[Unit]
Description=Alpha Automation FastAPI Service
After=network.target

[Service]
User=root
WorkingDirectory=/root/newrepo
Environment=AA_SECRET=replace-with-a-strong-secret
Environment=AA_COOKIE_SECURE=1
Environment=AA_AUTO_CREATE_ADMIN=1
Environment=AA_ADMIN_PASSWORD=admin123
ExecStart=/root/newrepo/.venv/bin/python -m uvicorn server:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Then enable and start it:
```bash
systemctl daemon-reload
systemctl enable alpha-automation
systemctl start alpha-automation
systemctl status alpha-automation
```

## Part 5: Use a reverse proxy (strongly recommended)

Install Nginx:
```bash
apt install -y nginx
```

Create `/etc/nginx/sites-available/alpha-automation`

```nginx
server {
    listen 80;
    server_name your-domain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable it:
```bash
ln -s /etc/nginx/sites-available/alpha-automation /etc/nginx/sites-enabled/
nginx -t
systemctl restart nginx
```

Use Certbot for HTTPS (optional):
```bash
apt install -y certbot python3-certbot-nginx
certbot --nginx -d your-domain.com
```

## Part 6: Admin and licensing workflow

### Admin access
- Login page: `http://<VPS_IP>:8000/admin/login`
- Default admin: `admin` / `admin123`
- Change password immediately.

### License key flow
- Generate licenses from `/admin/licenses/generate`.
- Use `/devices/register` to register a device to a key.
- Validate clients with `/licenses/validate`.
- Offer codes can be generated from `/admin/offers/generate` and redeemed on the client side.

## Part 7: Installer for local testing

Run this script to build a local package for testing:
```bash
./build_installer.sh
```

Then install locally by running:
```bash
cd dist/installer
./install.sh
./alpha_automation_server
```

## Notes
- For local testing only, `AA_ALLOW_INSECURE_SECRET=1` is acceptable.
- For VPS/public hosting, always set a real `AA_SECRET` and keep cookies secure.
