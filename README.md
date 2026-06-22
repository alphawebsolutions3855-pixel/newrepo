# Alpha-Automation
Minimal scaffold for the Alpha-Automation Facebook automation project.
Run the backend API (development):
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn server:app --reload --port 8000
```
For a fresh database, the app now bootstraps a default admin user with:
- username: `admin`
- password: `admin123`
If you are running locally over HTTP, set `AA_COOKIE_SECURE=0` so the admin login cookie is accepted by the browser.
Open the admin UI at `admin/index.html` (static demo) and use the API endpoints at `http://localhost:8000`.
### Change the default admin password
After first login, update the password to keep the app secure.
Using API token auth:
```bash
curl -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}'
```
```bash
TOKEN=$(curl -s -X POST http://localhost:8000/auth/token \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}' | jq -r '.access_token')
curl -X POST http://localhost:8000/admin/users/admin/set_password \
  -H "Authorization: Bearer $TOKEN" \
  -F "new_password=your_new_password"
```
Or via browser UI:
1. Log in at `http://localhost:8000/admin/login`
2. Go to `/admin/users/ui`
3. Update the `admin` password from the user management page
See the development flow and lifecycle in `DEV_FLOW.md`.
Run tests:
```bash
pip install -r requirements.txt
pytest
```
Build a standalone server and test locally:
```bash
./build_installer.sh
```

Windows build (create .exe on Windows):
```powershell
# Run on Windows PowerShell (in repo root)
python -m pip install --upgrade pip setuptools wheel pyinstaller
python -m pip install -r requirements.txt
.\build_installer_windows.ps1
```

To install and test on your PC before hosting, follow the steps in `VPS_HOSTING_GUIDE.md`.

Dashboard and Grafana/Prometheus Configuration
 -----------------------------------------------
 Would you like me to:
 - Secure the dashboard with auth and add real batch listing, or
 - Add Grafana dashboard JSON and scrape config?
 Both are implemented: secure dashboard endpoint `/admin/dashboard`, `/admin/batches` API (requires auth), Grafana dashboard JSON in `grafana/dashboard.json`, and Prometheus scrape example in `prometheus.yml`.
 To view the dashboard:
 1. Start the server and obtain a token via `/auth/token`.
 2. Use the token to GET `/admin/dashboard` with an `Authorization: Bearer <token>` header.
 Grafana:
 - Import `grafana/dashboard.json` into Grafana and add the Prometheus datasource that points to your Prometheus instance scraping `/metrics` as shown in `prometheus.yml`.
This project includes a Graph API client and endpoints to prepare and fire batches of posts to Pages or Groups. To use them you must:
- Create a Facebook App with required permissions (pages_manage_posts, pages_read_engagement, pages_manage_metadata, pages_read_user_content, groups_access_member_info as needed).
- Obtain a Page Access Token for the target page (long-lived token recommended).
- Set environment variables or pass tokens in the API request body for `page_id` and `page_token` when calling `/facebook/fire_batch`.
- Respect Facebook platform policies; prefer Graph API endpoints rather than automated UI scraping.
Example prepare + fire flow:
1. POST `/facebook/prepare_batch` with JSON {"name":"batch1","items":[{"message":"Hi","link":null,"media_urls":[]}]} and auth.
2. POST `/facebook/fire_batch` with JSON {"batch_id":1, "page_id":"<PAGE_ID>", "page_token":"<PAGE_ACCESS_TOKEN>"} and auth.
Note: The FB client uses `requests` with retries. In testing, mock the Graph API calls.
When the Graph API is not available
---------------------------------
This repository includes a browser-based UI automation fallback using Playwright (`fb_automator.py`) so you can drive Facebook UI flows directly. By default this runs in DRY mode (no browsers launched). To enable real automation:
- Install Playwright and browsers:
```bash
pip install -r requirements.txt
playwright install chromium
```
- Disable dry-run mode by exporting `AA_DRY_RUN=0` in the environment.
- Provide credentials or page URLs to the automator endpoints.
Cautions:
- UI automation can be fragile — selectors and flows change frequently. Use the adaptive handlers and `self_healer` to maintain selectors.
- Respect Facebook's terms and rate limits. Prefer running in staging/test environments.
# Alpha-Automation