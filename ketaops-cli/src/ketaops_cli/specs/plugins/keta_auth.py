"""KetaDB authentication plugin — two-step login with CSRF token."""

from cliyard.plugin import register_auth_step
from cliyard.client.http import HttpClient
import os


@register_auth_step("keta_login")
class KetaLogin:
    """KetaDB two-step authentication.

    Step 1: POST /api/v1/account/login → get X-Csrf-Token + JSESSIONID cookie
    Step 2: POST /api/v1/auth/tokens → get API token
    """

    def execute(self, auth_state: dict, config: dict, http_client: HttpClient) -> str:
        username = config.get("username") or os.environ.get("KETA_USER")
        password = config.get("password") or os.environ.get("KETA_PASS")

        if not username or not password:
            raise ValueError("KETA_USER and KETA_PASS must be set")

        # Step 1: Login
        login_resp = http_client.request(
            method="POST",
            url=config.get("login_endpoint", "/api/v1/account/login"),
            data={"username": username, "password": password},
        )
        login_data = login_resp.json()

        # Try common key names for the CSRF token
        csrf_token = (
            login_data.get("X-Csrf-Token")
            or login_data.get("csrfToken")
            or login_data.get("csrf_token")
        )
        if not csrf_token:
            raise ValueError("No X-Csrf-Token in login response")

        # Step 2: Create API token
        import time

        now_ms = int(time.time() * 1000)
        token_resp = http_client.request(
            method="POST",
            url=config.get("token_endpoint", "/api/v1/auth/tokens"),
            data={
                "username": username,
                "expireTime": now_ms + 31536000000,  # 1 year
                "notBefore": now_ms,
                "description": "created by ketaops-cli",
            },
            headers={"X-Csrf-Token": csrf_token},
        )
        token_data = token_resp.json()
        api_token = token_data.get("token")
        if not api_token:
            raise ValueError("No token in response")

        # Store in auth_state for inject step
        auth_state["token"] = api_token

        # Also inject into http_client headers
        http_client.default_headers["Authorization"] = f"Bearer {api_token}"

        return api_token
