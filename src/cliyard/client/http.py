from __future__ import annotations

import requests

from cliyard.engine.errors import ApiError


class HttpClient:
    """HTTP client wrapper with default headers and session persistence.

    Uses ``requests.Session()`` to maintain cookies (e.g. ``JSESSIONID``)
    across multiple requests in an auth chain.
    """

    def __init__(self, base_url: str) -> None:
        self.base_url = base_url.rstrip("/")
        self.default_headers: dict[str, str] = {}
        self._session = requests.Session()

    def request(
        self,
        method: str,
        url: str,
        data: dict | list | None = None,
        query_params: dict | None = None,
        headers: dict | None = None,
    ) -> requests.Response:
        """Send an HTTP request, prepending base_url for relative paths."""
        merged_headers: dict[str, str] = {**self.default_headers, **(headers or {})}
        send_json = isinstance(data, (dict, list)) and method.upper() in ("POST", "PUT", "PATCH")
        if send_json and "Content-Type" not in merged_headers:
            merged_headers["Content-Type"] = "application/json"
        if not url.startswith("http"):
            url = f"{self.base_url}{url}"
        resp = self._session.request(
            method,
            url,
            json=data,
            params=query_params,
            headers=merged_headers or None,
            timeout=30,
        )
        if 400 <= resp.status_code < 600:
            raise ApiError(status=resp.status_code, url=url, body=resp.text)
        return resp


def request(
    method: str,
    url: str,
    data: dict | list | None = None,
    query_params: dict | None = None,
    headers: dict | None = None,
    timeout: int = 30,
    files: dict | None = None,
) -> requests.Response:
    """Send an HTTP request.

    Args:
        method: HTTP method (GET, POST, PUT, DELETE, etc.)
        url: Full URL to call.
        data: JSON-serialisable body for POST/PUT/PATCH, or form data for multipart.
        query_params: URL query parameters.
        headers: Extra headers (merged with defaults).
        timeout: Timeout in seconds.
        files: File uploads for multipart requests. When provided, request is
            sent as multipart/form-data instead of JSON.

    Returns:
        requests.Response on 2xx.

    Raises:
        ApiError: On 4xx or 5xx responses.
        requests.RequestException: On connection / timeout errors.
    """
    merged_headers = dict(headers) if headers else {}

    if files is not None:
        # Force Content-Type for file upload (ketacli pattern: app/json)
        merged_headers.setdefault("Content-Type", "application/json")
        response = requests.request(
            method=method,
            url=url,
            data=data,
            files=files,
            params=query_params,
            headers=merged_headers or None,
            timeout=timeout,
        )
    else:
        send_json = isinstance(data, (dict, list)) and method.upper() in ("POST", "PUT", "PATCH")
        if send_json and "Content-Type" not in merged_headers:
            merged_headers["Content-Type"] = "application/json"

        response = requests.request(
            method=method,
            url=url,
            json=data if send_json else None,
            params=query_params,
            headers=merged_headers or None,
            timeout=timeout,
        )

    if 400 <= response.status_code < 600:
        raise ApiError(status=response.status_code, url=url, body=response.text)

    return response
