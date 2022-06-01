import base64
import logging
from typing import Any
import aiohttp

_LOGGER = logging.getLogger(__name__)
class SessionManager:
    HEADER_CONTENT_TYPE_URLENCODED = 'application/x-www-form-urlencoded'
    HEADER_USER_AGENT = "okhttp/3.12.1"
    HEADER_BUNDLE_NAME = "com.geniecompany.AladdinConnect"
    HEADER_BUILD_VERSION = "2042"
    HEADER_APP_VERSION = "5.30"

    API_BASE_URL = "https://pxdqkls7aj.execute-api.us-east-1.amazonaws.com/Android"
    RPC_URL = API_BASE_URL

    LOGIN_ENDPOINT = "/oauth/token"
    X_API_KEY = "fkowarQ0dX9Gj1cbB9Xkx1yXZkd6bzVn5x24sECW"
    

    

    def __init__(self, email, password):
        self._timeout = aiohttp.ClientTimeout(total=30)
        self._session = aiohttp.ClientSession(timeout = self._timeout)
        self._headers = {'Content-Type': self.HEADER_CONTENT_TYPE_URLENCODED,
                                      'AppVersion': self.HEADER_APP_VERSION,
                                      'BundleName': self.HEADER_BUNDLE_NAME,
                                      'User-Agent': self.HEADER_USER_AGENT,
                                      'BuildVersion': self.HEADER_BUILD_VERSION,
                                      'X-Api-Key': self.X_API_KEY}
        self._auth_token = None
        self._user_email = email
        self._password = password
        self._logged_in = False
    

    def auth_token(self):
        return self._auth_token

    def set_auth_token(self,auth_token):
        self._auth_token = auth_token
        self._headers.update({'Authorization': f'Bearer {self._auth_token}'})


    async def login(self):
        self._auth_token = None
        self._logged_in = False
        password_base64 = base64.b64encode(self._password.encode('utf-8')).decode('utf-8')
        payload = {"grant_type": "password",
                    "client_id": "1000",
                    "brand": "ALADDIN",
                    "username": self._user_email,
                    "password": password_base64,
                    "platform": "platform",
                    "model": "Google Pixel 6",
                    "app_version": "5.30",
                    "build_number": "2042",
                    "os_version": "12.0.0"}


        url = self.API_BASE_URL + self.LOGIN_ENDPOINT
        try:
            response = await self._session.post(url ,data=payload,headers=self._headers)

            if response.content_type == "application/json":
                response_json = await response.json()

            if response_json and "access_token" in response_json:
                self._logged_in = True
                self._auth_token = response_json["access_token"]
                self._headers.update({'Authorization': f'Bearer {self._auth_token}'})
                return True
        except ValueError as ex:
            _LOGGER.error("Aladdin Connect - Unable to login %s", ex)

        return False

    async def close(self):
        if self._session:
            await self._session.close()

    async def get(self,endpoint:str):
        url = self.API_BASE_URL + endpoint
        self._headers.update({'Content-Type': 'application/x-www-form-urlencoded'})
        try:
            response = await self._session.get(url ,headers=self._headers)
            if response:
                _LOGGER.debug(f"Get message: {response}")

            if response.content_type == "application/json":
                return await response.json()

        except ValueError as ex:
            _LOGGER.error("Aladdin Connect - Unable to get doors %s : %s", ex, response)
        
        if response.status == 401:
            raise aiohttp.ClientConnectionError("Key has expired")        
        return None

    async def call_rpc(self,api, payload=None):
        self._headers.update({'Content-Type': 'application/json'})
        url = self.API_BASE_URL + api
        try:
            response = await self._session.post(url,json=payload,headers=self._headers)
        
        except ValueError as ex:
            _LOGGER.error("Aladdin Connect - Unable to operate doors %s", ex)
        
        if response.status not in (200, 204):
            msg = f"Aladdin API call ({url}) failed: {response.status}, {await response.read()}"
            raise ValueError(msg)
        
        if response.content_type == "application/json":
            return await response.json()
        
        return None

    async def call_status(self,api, payload=None):
        self._headers.update({'Content-Type': 'application/json'})
        url = self.API_BASE_URL + api
        try:
            response = await self._session.get(url,headers=self._headers)
        
        except ValueError as ex:
            _LOGGER.error("Aladdin Connect - Unable to listen to doors %s", ex)

        if response.status in (401):
            msg = f"Aladdin API call ({url}) failed: {response.status}, {response.text}"
            raise aiohttp.ClientConnectionError(msg)
            
        if response.status not in (200, 204):
            msg = f"Aladdin API call ({url}) failed: {response.status}, {response.text}"
            raise ValueError(msg)
        
        if response.content_type == "application/json":
            return await response.json()
        
        return None

