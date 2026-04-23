from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from modules.config_manager import config_manager
from utils.models import ProxyConfig

logger = logging.getLogger(__name__)


def async_client_kwargs_from_requests_proxies(
    proxies: dict | None,
    *,
    timeout: float | None = None,
) -> dict[str, Any]:
    """
    Build keyword args for ``httpx.AsyncClient`` (httpx >= 0.28 removed ``proxies=``).
    ``proxies`` uses requests-style keys ``http`` / ``https``.
    """
    kwargs: dict[str, Any] = {}
    if timeout is not None:
        kwargs["timeout"] = timeout
    if not proxies:
        return kwargs
    http_p = str(proxies.get("http") or "").strip() or None
    https_p = str(proxies.get("https") or "").strip() or None
    if not http_p and not https_p:
        return kwargs
    if http_p and https_p and http_p != https_p:
        kwargs["mounts"] = {
            "http://": httpx.AsyncHTTPTransport(proxy=http_p),
            "https://": httpx.AsyncHTTPTransport(proxy=https_p),
        }
    else:
        url = https_p or http_p
        assert url is not None
        kwargs["mounts"] = {
            "http://": httpx.AsyncHTTPTransport(proxy=url),
            "https://": httpx.AsyncHTTPTransport(proxy=url),
        }
    return kwargs


def async_client_kwargs_from_proxy_config(
    proxy_config: Optional[ProxyConfig] = None,
    *,
    timeout: float | None = None,
) -> dict[str, Any]:
    """Same as :func:`async_client_kwargs_from_requests_proxies` but from a :class:`ProxyConfig`."""
    if not proxy_config or (not proxy_config.http and not proxy_config.https):
        return async_client_kwargs_from_requests_proxies(None, timeout=timeout)
    req_style: dict[str, str] = {}
    if proxy_config.http:
        req_style["http"] = proxy_config.http
    if proxy_config.https:
        req_style["https"] = proxy_config.https
    return async_client_kwargs_from_requests_proxies(req_style, timeout=timeout)


async def preflight_network_check() -> bool:
    """
    Checks network connectivity for both direct and proxy connections (if configured).
    Returns True if network is fully reachable, False otherwise.
    """
    timeout = 5.0
    direct_url = "https://www.douyin.com"
    
    # Check direct connection
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            await client.head(direct_url, follow_redirects=True)
    except httpx.RequestError as exc:
        logger.warning("network reachable probe failed for direct link: %s", exc)
        return False

    # Check proxy connection
    proxies = config_manager.get_proxies()
    if proxies:
        proxy_url = "https://www.youtube.com"
        try:
            client_kw = async_client_kwargs_from_requests_proxies(proxies, timeout=timeout)
            async with httpx.AsyncClient(**client_kw) as client:
                await client.head(proxy_url, follow_redirects=True)
        except httpx.RequestError as exc:
            logger.warning("network reachable probe failed for proxy link: %s", exc)
            return False

    return True
