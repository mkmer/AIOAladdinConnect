import base64
import logging
import socket
import aiohttp


_LOGGER = logging.getLogger(__name__)


class SessionManager:
    HEADER_CONTENT_TYPE_URLENCODED = "application/x-www-form-urlencoded"
    API_BASE_URL = "https://pxdqkls7aj.execute-api.us-east-1.amazonaws.com/Android"
    # API_BASE_URL = "https://16375mc41i.execute-api.us-east-1.amazonaws.com/IOS"
    RPC_URL = API_BASE_URL

    LOGIN_ENDPOINT = "/oauth/token"
    LOGOUT_ENDPOINT = "/session/logout"
    X_API_KEY = "fkowarQ0dX9Gj1cbB9Xkx1yXZkd6bzVn5x24sECW"  # Android
    # X_API_KEY = "2BcHhgzjAa58BXkpbYM977jFvr3pJUhH52nflMuS" # IOS

    def __init__(self, email, password, session, client_id):
        self._timeout = aiohttp.ClientTimeout(total=30)
        self._session = session
        self._headers = {
            "Content-Type": self.HEADER_CONTENT_TYPE_URLENCODED,
            "X-Api-Key": self.X_API_KEY,
        }
        self._auth_token = None
        self._user_email = email
        self._password = password
        self._logged_in = False
        self._client_id = client_id
        self._expires_in = None

    def auth_token(self):
        """Retrieve current auth token."""
        return self._auth_token

    def set_auth_token(self, auth_token):
        """Set auth token after logging in."""
        self._auth_token = auth_token
        self._headers.update({"Authorization": f"Bearer {self._auth_token}"})

    async def login(self) -> bool:
        """Login to Aladdin Connect service."""
        self._auth_token = None
        self._logged_in = False
        password_base64 = base64.b64encode(self._password.encode("utf-8")).decode(
            "utf-8"
        )
        payload = {
            "grant_type": "password",
            "client_id": self._client_id,
            "brand": "ALADDIN",
            "username": self._user_email,
            "password": password_base64,
            "app_version": "5.30",
            # "platform": "platform",
            # "model": "Google Pixel 6",
            # "build_number": "2042",
            # "os_version": "12.0.0"
        }

        url = self.API_BASE_URL + self.LOGIN_ENDPOINT
        _LOGGER.debug("Sending payload: %s", payload)
        try:
            response = await self._session.post(
                url, data=payload, headers=self._headers
            )
            _LOGGER.debug("Received Response: %s", response)
            if response.status == 401:
                raise InvalidPasswordError(f"Server reported bad login {response}")

            elif response.status != 200:
                raise ConnectionError(f"Server reported Error {response}")
            if response.content_type == "application/json":
                response_json = await response.json()
                _LOGGER.debug("JSON Response %s", response_json)

            if response_json and "access_token" in response_json:
                self._logged_in = True
                self._auth_token = response_json["access_token"]
                self._expires_in = response_json["expires_in"]
                self._headers.update({"Authorization": f"Bearer {self._auth_token}"})
                return True
        except ValueError as ex:
            _LOGGER.error("Aladdin Connect - Unable to login %s", ex)
        # aiohttp.client_exceptions.ClientConnectorError - do we need to catch this?
        except InvalidPasswordError as ex:
            _LOGGER.error("Aladdin Connect - Unable to connect for login %s", ex)
            raise ex

        return False

    async def close(self):
        """Close socket."""
        _LOGGER.debug("Logging out & closing socket")
        if self._session:
            self._headers.update({"Content-Type": "application/json"})
            url = self.API_BASE_URL + self.LOGOUT_ENDPOINT
            response = await self._session.post(url, headers=self._headers)
            if response.status != 200:
                raise ConnectionError("Server reported Error %s" % response)
            await self._session.close()

    async def get(self, endpoint: str):
        """Get door status."""
        url = self.API_BASE_URL + endpoint
        self._headers.update({"Content-Type": "application/x-www-form-urlencoded"})

        try:
            _LOGGER.info("Updating door status")
            response = await self._session.get(url, headers=self._headers)
            if response:
                _LOGGER.debug("Get message: %s", await response.text())

            if response.content_type == "application/json":
                return await response.json()

        except ValueError as ex:
            _LOGGER.error("Aladdin Connect - Unable to get doors %s : %s", ex, response)

        except socket.gaierror as ex:
            _LOGGER.error("Socket Connection error %s", ex)

        if response.status != 200:
            raise ConnectionError("Key has expired or not valid")
        return None

    async def call_rpc(self, api, payload=None):
        """Send and RPC message."""
        self._headers.update({"Content-Type": "application/json"})
        url = self.API_BASE_URL + api
        try:
            _LOGGER.info(f"Sending message: {payload}")
            response = await self._session.post(
                url, json=payload, headers=self._headers
            )

        except ValueError as ex:
            _LOGGER.error("Aladdin Connect - Unable to operate doors %s", ex)

        if response.status not in (200, 204):
            msg = f"Aladdin API call ({url}) failed: {response.status}, {await response.read()}"
            raise ValueError(msg)

        if response.content_type == "application/json":
            return await response.json()

        return None

    async def call_status(self, api, payload=None):
        """Update the door status."""
        self._headers.update({"Content-Type": "application/json"})
        url = self.API_BASE_URL + api
        try:
            response = await self._session.get(url, headers=self._headers)

        except ValueError as ex:
            _LOGGER.error("Aladdin Connect - Unable to listen to doors %s", ex)

        except socket.gaierror as ex:
            _LOGGER.error("Socket Connect error %s", ex)

        if response.status in (401):
            msg = f"Aladdin API call ({url}) failed: {response.status}, {await response.text()}"
            raise ConnectionError(msg)

        if response.status not in (200, 204):
            msg = f"Aladdin API call ({url}) failed: {response.status}, {await response.text()}"
            raise ValueError(msg)

        if response.content_type == "application/json":
            return await response.json()

        msg = (
            f"Aladdin API call ({url}) incorrect content type: {response.content_type}"
        )
        raise ValueError(msg)


class InvalidPasswordError(Exception):
    """Aladdin Password Error."""


class ConnectionError(Exception):
    """Aladdin Connection error."""
