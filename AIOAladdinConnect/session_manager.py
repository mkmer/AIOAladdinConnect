import base64
import logging
from typing import Any
import aiohttp

_LOGGER = logging.getLogger(__name__)
class SessionManager:
    HEADER_CONTENT_TYPE_URLENCODED = 'application/x-www-form-urlencoded'

    API_BASE_URL = "https://pxdqkls7aj.execute-api.us-east-1.amazonaws.com/Android"
    #API_BASE_URL = "https://16375mc41i.execute-api.us-east-1.amazonaws.com/IOS"
    RPC_URL = API_BASE_URL

    LOGIN_ENDPOINT = "/oauth/token"
    LOGOUT_ENDPOINT = "/session/logout"
    X_API_KEY = "fkowarQ0dX9Gj1cbB9Xkx1yXZkd6bzVn5x24sECW" #Android
    #X_API_KEY = "2BcHhgzjAa58BXkpbYM977jFvr3pJUhH52nflMuS" # IOS
    

    

    def __init__(self, email, password, session, client_id):
        self._timeout = aiohttp.ClientTimeout(total=30)
        self._session = session
        self._headers = {'Content-Type': self.HEADER_CONTENT_TYPE_URLENCODED,
                                      'X-Api-Key': self.X_API_KEY}
        self._auth_token = None
        self._user_email = email
        self._password = password
        self._logged_in = False
        self._client_id = client_id
    

    def auth_token(self):
        return self._auth_token

    def set_auth_token(self,auth_token):
        self._auth_token = auth_token
        self._headers.update({'Authorization': f'Bearer {self._auth_token}'})


    async def login(self) -> bool:
        self._auth_token = None
        self._logged_in = False
        password_base64 = base64.b64encode(self._password.encode('utf-8')).decode('utf-8')
        payload = {"grant_type": "password",
                    "client_id": self._client_id,
                    "brand": "ALADDIN",
                    "username": self._user_email,
                    "password": password_base64,
                    "app_version": "5.30",
                    #"platform": "platform",
                    #"model": "Google Pixel 6",
                    #"build_number": "2042",
                    #"os_version": "12.0.0"
                    }


        url = self.API_BASE_URL + self.LOGIN_ENDPOINT
        _LOGGER.debug(f"Sending paylod: {payload}")
        try:
            response = await self._session.post(url ,data=payload,headers=self._headers)
            _LOGGER.debug(f"Received Response: {response}")
            if response.status != 200:
                raise aiohttp.ClientConnectionError(f"Server reported Error {response}")
            if response.content_type == "application/json":
                response_json = await response.json()
                _LOGGER.debug(f"JSON Response {response_json}")

            if response_json and "access_token" in response_json:
                self._logged_in = True
                self._auth_token = response_json["access_token"]
                self._headers.update({'Authorization': f'Bearer {self._auth_token}'})
                return True
        except ValueError as ex:
            _LOGGER.error("Aladdin Connect - Unable to login %s", ex)

        return False

    async def close(self):
        _LOGGER.debug("Logging out & closing socket")
        if self._session:
            self._headers.update({'Content-Type' : 'application/json'})
            url = self.API_BASE_URL + self.LOGOUT_ENDPOINT
            response = await self._session.post(url ,headers=self._headers)
            if response.status != 200:
                raise aiohttp.ClientConnectionError(f"Server reported Error {response}")
            await self._session.close()

    async def get(self,endpoint:str):
        url = self.API_BASE_URL + endpoint
        self._headers.update({'Content-Type': 'application/x-www-form-urlencoded'})
        try:
            _LOGGER.info("Updating door status")
            response = await self._session.get(url ,headers=self._headers)
            if response:
                _LOGGER.debug(f"Get message: {await response.text()}")

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
            _LOGGER.info (f"Sending message: {payload}")
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
            msg = f"Aladdin API call ({url}) failed: {response.status}, {await response.text()}"
            raise aiohttp.ClientConnectionError(msg)
            
        if response.status not in (200, 204):
            msg = f"Aladdin API call ({url}) failed: {response.status}, {await response.text()}"
            raise ValueError(msg)
        
        if response.content_type == "application/json":
            return await response.json()
        
        msg = f"Aladdin API call ({url}) incorrect content type: {response.content_type}"
        raise ValueError(msg)
        

