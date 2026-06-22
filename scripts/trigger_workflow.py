#!/usr/bin/env python3
"""
Trigger the GitHub Actions workflow dispatch for this repository.

Usage:
  export GITHUB_TOKEN=ghp_....
  python scripts/trigger_workflow.py

Requires: GITHUB_TOKEN with `repo` and `workflow` scopes.
"""
import os
import requests

token = os.environ.get('GITHUB_TOKEN')
if not token:
    print('Set GITHUB_TOKEN env var with a Personal Access Token that has workflow permissions')
    raise SystemExit(1)

owner = 'alphawebsolutions3855-pixel'
repo = 'newrepo'
workflow_id = 'build_artifacts.yml'

url = f'https://api.github.com/repos/{owner}/{repo}/actions/workflows/{workflow_id}/dispatches'
resp = requests.post(url, json={'ref':'main'}, headers={'Authorization':f'token {token}', 'Accept':'application/vnd.github+json'})
print(resp.status_code, resp.text)
if resp.status_code == 204:
    print('Workflow dispatched')
else:
    print('Failed to dispatch workflow')
