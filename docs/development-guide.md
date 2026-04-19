# Development & Testing Guide

## Prerequisites
- Python 3.9+
- OS: Win / Mac / Linux headless
- Global HTTP Proxy (if residing in local firewalled networks restricting GCP IPs)

## Setup Steps
1. Checkout code
2. Run `pip install -r requirements.txt`
3. Setup `config.json` manually at project root level and place `client_secret.json`.

## Testing Modules
We have modular testing configured bypassing APScheduler logic.
```bash
python test_pipeline.py fetcher
python test_pipeline.py database
python test_pipeline.py downloader
python test_pipeline.py e2e
```
Also python standard Unittests cover core classes:
```bash
python -m unittest discover -s tests
```

## Running Production Service
Leave it in the background running persistently:
```bash
python main.py
```
