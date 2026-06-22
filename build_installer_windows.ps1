# PowerShell helper to build a Windows standalone executable using PyInstaller
# Run this on a Windows machine (or Windows runner).
# Requires Python 3.8+ and access to the repo files.

Set-StrictMode -Version Latest

Write-Host "Installing build dependencies..."
python -m pip install --upgrade pip setuptools wheel pyinstaller
python -m pip install -r requirements.txt

# Create dist folder
if (Test-Path dist) { Remove-Item -Recurse -Force dist }

# Build a single exe (console). Adjust --noconsole for GUI.
pyinstaller --onefile --name alpha_automation_server server.py

# Prepare installer folder
New-Item -ItemType Directory -Path dist\installer -Force | Out-Null
Copy-Item -Path dist\alpha_automation_server.exe -Destination dist\installer\
Copy-Item -Path requirements.txt -Destination dist\installer\
Copy-Item -Path README.md -Destination dist\installer\

Write-Host "Windows standalone created in dist\\installer\"