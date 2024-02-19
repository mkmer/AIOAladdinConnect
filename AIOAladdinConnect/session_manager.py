"""Aladdin Connect Session Manager."""
import base64
import hmac
import hashlib
import socket
import asyncio
import aiohttp
import aioboto3
from .const import _LOGGER, CLIENT_ID, CLIENT_SECRET, API_BASE_URL

TIME_BUFFER = 120

class SessionManager:
    """A session Manager for Aladdin Connect."""

    def __init__(self, email, password, session, client_id):
        self._timeout = aiohttp.ClientTimeout(total=30)
        self._session = session
        self._headers = {
            'app_version': '6.21',
            'Host':API_BASE_URL[8:],
            'User-Agent': 'okhttp/4.10.0',        
        }
        self._auth_token = None
        self._user_email = email
        self._password = password
        self._logged_in = False
        self._client_id = client_id if client_id else CLIENT_ID
        self._expires_in = None
        self._id_token = ""
        self._refresh_token = ""
        self._auth = {}
        self._reauthtimer = None
        self._cidp = None
        self._cidpsession = None

    def get_secret_hash(self, username):
        """Get the secret hash."""
        msg = username + self._client_id
        dig = hmac.new(
            str(CLIENT_SECRET).encode('utf-8'),
            msg = str(msg).encode('utf-8'),
            digestmod=hashlib.sha256).digest()
        d2 = base64.b64encode(dig).decode()
        return d2

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
        try:
            #May need to figure out different regions?
            cidpsession = aioboto3.Session()
            self._cidpsession = cidpsession
            async with cidpsession.client('cognito-idp',region_name="us-east-2") as cidp:
                response = await cidp.initiate_auth(
                    AuthFlow='USER_PASSWORD_AUTH',
                    AuthParameters={
                        "SECRET_HASH":self.get_secret_hash(self._user_email),
                        "USERNAME":self._user_email,
                        "PASSWORD":self._password,
                    },
                    ClientId=CLIENT_ID,
                )

        except ValueError as ex:
            _LOGGER.error("Aladdin Connect - Unable to login %s", ex)
            raise ex
        # aiohttp.client_exceptions.ClientConnectorError - do we need to catch this?
        except InvalidPasswordError as ex:
            _LOGGER.error("Aladdin Connect - Unable to connect for login %s", ex)
            raise ex

        _LOGGER.debug("Received CIDP Response: %s", response)
        if response and response.get('AuthenticationResult'):
            _LOGGER.debug("JSON Response %s", response['AuthenticationResult'])
            self._auth = response['AuthenticationResult']
            self._logged_in = True
            self._auth_token = response['AuthenticationResult']['AccessToken']
            self._expires_in = response['AuthenticationResult']['ExpiresIn']
            self._id_token = response['AuthenticationResult']['IdToken']
            self._refresh_token = response['AuthenticationResult']['RefreshToken']
            self._headers.update({"Authorization": f"Bearer {self._auth_token}"})
            self._reauthtimer = ReauthTimer((self._expires_in - TIME_BUFFER), self.reauth)
            return True

        return False

    async def close(self):
        """Close socket."""
        _LOGGER.debug("Logging out & closing socket")
        #Do nothing for now. Need to find logout endpoint.
  
    async def get(self, endpoint: str):
        """Get door status."""
        url = API_BASE_URL + endpoint
        self._headers.update({"Content-Type": "application/x-www-form-urlencoded"})

        try:
            _LOGGER.info("Updating door status")
            response = await self._session.get(url, headers=self._headers)
            if response:
                _LOGGER.debug("Get message: %s", await response.text())

            if response.content_type == "application/json":
                return await response.json()

        except ValueError as ex:
            _LOGGER.error("Aladdin Connect - Unable to get doors %s", ex)

        except socket.gaierror as ex:
            _LOGGER.error("Socket Connection error %s", ex)

        if response and response.status != 200:
            raise ConnectionError("Key has expired or not valid")
        return None

    async def call_rpc(self, api, payload=None):
        """Send and RPC message."""
        self._headers.update({"Content-Type": "application/json"})
        url = API_BASE_URL + api
        try:
            _LOGGER.info("Sending message: %s", payload)
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

    async def call_status(self, api):
        """Update the door status."""
        self._headers.update({"Content-Type": "application/json"})
        url = API_BASE_URL + api
        try:
            response = await self._session.get(url, headers=self._headers)

        except ValueError as ex:
            _LOGGER.error("Aladdin Connect - Unable to listen to doors %s", ex)

        except socket.gaierror as ex:
            _LOGGER.error("Socket Connect error %s", ex)

        if response.status in (401, 403):
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

    async def reauth(self) -> bool:
        """Reauthenticate client."""
        async with self._cidpsession.client('cognito-idp',region_name="us-east-2") as cidp:
            try:
                response = await cidp.initiate_auth(
                        AuthFlow='REFRESH_TOKEN',
                        AuthParameters={
                            "SECRET_HASH":self.get_secret_hash(self._user_email),
                            "REFRESH_TOKEN":self._refresh_token,
                        },
                        ClientId=CLIENT_ID,
                    )
            except self._cidp.exceptions.NotAuthorizedException as ex:
                _LOGGER.debug("can't refresh token: %s", ex)
                return False

        _LOGGER.debug("Received CIDP Response: %s", response)
        if response['AuthenticationResult']:
            _LOGGER.debug("JSON Response %s", response['AuthenticationResult'])
            self._logged_in = True
            self._auth_token = response['AuthenticationResult']['AccessToken']
            self._expires_in = response['AuthenticationResult']['ExpiresIn']
            self._headers.update({"Authorization": f"Bearer {self._auth_token}"})

        self._reauthtimer = ReauthTimer((self._expires_in - TIME_BUFFER), self.reauth)
        return True

class ReauthTimer:
    """Reauth timer."""
    def __init__(self, timeout, callback):
        self._timeout = timeout
        self._callback = callback
        self._task = asyncio.ensure_future(self._job())

    async def _job(self):
        await asyncio.sleep(self._timeout)
        await self._callback()

    def cancel(self):
        """Cancel the timer."""
        self._task.cancel()

class InvalidPasswordError(Exception):
    """Aladdin Password Error."""


class AladdinConnectionError(Exception):
    """Aladdin Connection error."""
