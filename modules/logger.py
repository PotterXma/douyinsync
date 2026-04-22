import logging

# Proxy the logger to the globally configured douyinsync logger
# The actual setup/handlers are injected by utils/logger.py in main.py
logger = logging.getLogger("douyinsync")
