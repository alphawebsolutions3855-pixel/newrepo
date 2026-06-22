#!/usr/bin/env bash
set -euo pipefail

echo "Building local distribution artifacts and packaging for Windows installer"
python -m pip install --upgrade pip setuptools wheel pyinstaller
python -m pip install -r requirements.txt

if [ -d dist ]; then
  rm -rf dist
fi

python -m PyInstaller --onefile --name alpha_automation_server server.py
mkdir -p dist/installer
cp dist/alpha_automation_server dist/installer/
cp requirements.txt dist/installer/
cp README.md dist/installer/

cat > dist/installer/install.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
python -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
chmod +x alpha_automation_server
echo "Installation complete. Run ./alpha_automation_server"
EOF
chmod +x dist/installer/install.sh

echo "Standalone package created in dist/installer"
