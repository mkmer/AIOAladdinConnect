"""Aladdin Connect Session Manager."""
import base64
import logging
import boto3
import hmac
import hashlib
import uuid
import socket
import aiohttp
from .const import _LOGGER, CLIENT_ID, CLIENT_SECRET

class SessionManager:
    """A session Manager for Aladdin Connect."""
    HEADER_CONTENT_TYPE_URLENCODED = "application/x-www-form-urlencoded"
    API_BASE_URL = "https://api.smartgarage.systems"
    # API_BASE_URL = "https://16375mc41i.execute-api.us-east-1.amazonaws.com/IOS"
    RPC_URL = API_BASE_URL

    #LOGIN_ENDPOINT = "/oauth/token"
    LOGIN_ENDPOINT = "https://cognito-idp.us-east-2.amazonaws.com/"
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

        def get_secret_hash(username):
            """Get the secret hash."""
            msg = username + CLIENT_ID
            dig = hmac.new(
                str(CLIENT_SECRET).encode('utf-8'),
                msg = str(msg).encode('utf-8'),
                digestmod=hashlib.sha256).digest()
            d2 = base64.b64encode(dig).decode()
            return d2

        headers = {
                    "Content-Type": "application/x-amz-json-1.1",
                    "Accept-Encoding": "identity",
                    #"aws-sdk-invocation-id": "c4e03fa8-a542-4079-b19b-28c3b6e9be63",
                    "Connection": "Keep-Alive",
                    "Host": "cognito-idp.us-east-2.amazonaws.com",
                    "User-Agent": "amplify-android/1.37.3 (Android 12; Google Pixel 3; en_US)",
                    "X-Amz-Target" : "AWSCognitoIdentityProviderService.InitiateAuth"
                }

        try:
            cidp = boto3.client('cognito-idp',region_name="us-east-2")
            response = cidp.initiate_auth(
                AuthFlow='USER_PASSWORD_AUTH',
                AuthParameters={
                    "SECRET_HASH":get_secret_hash(self._user_email),
                    "USERNAME":self._user_email,
                    "PASSWORD":self._password,
                },
                ClientId=CLIENT_ID,
            )
        
            _LOGGER.debug("Received Response: %s", response)
            if response['AuthenticationResult']:
                _LOGGER.debug("JSON Response %s", response['AuthenticationResult'])
                self._logged_in = True
                self._auth_token = response['AuthenticationResult']['AccessToken']
                self._expires_in = response['AuthenticationResult']['ExpiresIn']
                self._IdToken = response['AuthenticationResult']['IdToken']
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
                raise ConnectionError(f"Server reported Error {response}")
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
        url = self.API_BASE_URL + api
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


class InvalidPasswordError(Exception):
    """Aladdin Password Error."""


class ConnectionError(Exception):
    """Aladdin Connection error."""
