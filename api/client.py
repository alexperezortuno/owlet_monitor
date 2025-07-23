import csv
import os
import platform
import sys
import time
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from traceback import format_exception
from typing import Optional, Dict, Any, List
from urllib.parse import urljoin

import aiohttp
from aiohttp import ClientResponse

from api.utils import VitalsAnalyzer, vitals_from_dict
from exceptions import OwletError
from utils.config import Config


logger = logging.getLogger(__name__)

@dataclass
class AuthResponse:
    id_token: str
    mini_token: str
    access_token: str
    expires_in: int

@dataclass
class DeviceEndpoints:
    dsn: str
    properties_url: str
    activate_url: str

class DeviceManager:
    def __init__(self):
        self.devices: List[DeviceEndpoints] = []

    def add_device(self, device: DeviceEndpoints) -> None:
        self.devices.append(device)

    def clear_devices(self) -> None:
        self.devices.clear()

    def set_devices(self, devices: List[DeviceEndpoints]) -> None:
        self.devices = devices



class OwletClient:
    ANDROID_HEADERS = {
        'X-Android-Package': 'com.owletcare.owletcare',
        'X-Android-Cert': '2A3BC26DB0B8B0792DBE28E6FFDC2598F9B12B74'
    }

    analyzer: VitalsAnalyzer | None = None

    def __init__(self, config: Config = None):
        self.config = config
        self._session: Optional[aiohttp.ClientSession] = None
        self.analyzer = VitalsAnalyzer()
        self.devices = DeviceManager()

    def log(self, s) -> None:
        sys.stderr.write(s + '\n')
        sys.stderr.flush()

    def record(self, s) -> None:
        sys.stdout.write(s + '\n')
        sys.stdout.flush()

    async def fetch_dsn_async(self) -> List[DeviceEndpoints]:
        """
        Fetches Device Serial Numbers (DSN) and related endpoints for all available Owlet monitors.

        Returns:
            List[DeviceEndpoints]: List of device endpoints for each found monitor

        Raises:
            OwletError: If no Owlet monitors are found or if the request fails
        """
        if self.config.get_dsn():
            logger.debug("Using cached DSN information")
            return

        try:
            logger.info("Fetching device information")

            # Construct base URL for the API request
            base_url = self.config.get_region_config().get('url_base')
            devices_url = f"{base_url}/devices.json"

            # Fetch devices information
            response: ClientResponse = await self._make_request(
                'GET',
                devices_url,
                headers=self.config.get_headers()
            )

            if not response:
                raise OwletError('No response received from devices endpoint')

            devices: list = []
            for d in response:
                devices.append(d.get('device', {}))

            if not devices:
                raise OwletError('Found zero Owlet monitors')

            # Clear existing device information
            self.config.set_dsn([])
            self.config.set_props([])
            self.config.set_activate([])

            # Process each device
            for device in devices:
                device_sn = device.get('dsn')
                if not device_sn:
                    logger.warning("Found device without DSN, skipping")
                    continue

                # Create endpoint URLs for the device
                device_endpoints = DeviceEndpoints(
                    dsn=device_sn,
                    properties_url=f"{base_url}/dsns/{device_sn}/properties.json",
                    activate_url=f"{base_url}/dsns/{device_sn}/properties/APP_ACTIVE/datapoints.json"
                )

                # Update configuration with new device information
                self.config.append_dsn(device_endpoints.dsn)
                self.config.append_props(device_endpoints.properties_url)
                self.config.append_activate(device_endpoints.activate_url)

                logger.info(
                    f'Found Owlet monitor device serial number {device_endpoints.dsn}'
                )

            logger.info(f'Successfully fetched {len(devices)} devices')
            self.devices.set_devices(devices)
            return devices

        except aiohttp.ClientError as e:
            logger.error(f"Network error while fetching DSN: {e}")
            raise OwletError(f"Failed to fetch device information: {str(e)}") from e

        except Exception as e:
            logger.error(f"Unexpected error while fetching DSN: {e}")
            raise OwletError(f"Unexpected error: {str(e)}") from e

    def fetch_dsn(self):
        if len(self.config.get_dsn()) == 0:
            self.log('Getting DSN')
            r = self.config.get_session().get(self.config.get_region_config().get('url_base') + '/devices.json',
                                            headers=self.config.get_headers())
            r.raise_for_status()
            devs = r.json()
            if len(devs) < 1:
                raise OwletError('Found zero Owlet monitors')
            # Allow for multiple devices
            self.config.set_dsn([])
            self.config.set_props([])
            self.config.set_activate([])
            for device in devs:
                device_sn = device['device']['dsn']
                self.config.append_dsn(device_sn)
                self.log(f'Found Owlet monitor device serial number {device_sn}')
                self.config.append_props(
                    f"{self.config.get_region_config().get('url_base')}/dsns/{device_sn}/properties.json"
                )
                self.config.append_activate(
                    f"{self.config.get_region_config().get('url_base')}/dsns/{device_sn}/properties/APP_ACTIVE/datapoints.json"
                )

    def reactivate(self, url_activate):
        payload = {"datapoint": {"metadata": {}, "value": 1}}
        r = self.config.get_session().post(url_activate,
                                           json=payload,
                                           headers=self.config.get_headers())
        r.raise_for_status()

    def fetch_props(self):
        # Ayla cloud API data is updated only when APP_ACTIVE periodically reset to 1.
        my_props = []
        # Get properties for each device; note no pause between requests for each device
        for device_sn, next_url_activate, next_url_props in zip(self.config.get_dsn(), self.config.get_activate(),
                                                                self.config.get_props()):
            self.reactivate(next_url_activate)
            device_props = {'DSN': device_sn}
            r = self.config.get_session().get(next_url_props, headers=self.config.get_headers())
            r.raise_for_status()
            props = r.json()
            for prop in props:
                n = prop['property']['name']
                del (prop['property']['name'])
                device_props[n] = prop['property']
            my_props.append(device_props)
        return my_props

    def clear_screen(self):
        if platform.system() == "Windows":
            os.system('cls')
        else:
            os.system('clear')

    def save_to_csv(data):
        filename = 'owlet_data.csv'
        file_exists = os.path.isfile(filename)

        with open(filename, mode='a', newline='') as file:
            writer = csv.DictWriter(file, fieldnames=data.keys())

            # Escribir encabezados solo si el archivo es nuevo
            if not file_exists:
                writer.writeheader()

            writer.writerow(data)

    def record_vitals(self, p):
        try:
            device_sn = p['DSN']
            real_time_vitals = p.get('REAL_TIME_VITALS')

            if real_time_vitals is None:
                self.log(f"No real-time vitals available for device {device_sn}")
                return

            vitals_value = real_time_vitals.get('value')
            if not isinstance(vitals_value, dict):
                # Try parsing as JSON if it's a string
                try:
                    if isinstance(vitals_value, str):
                        vitals_value = json.loads(vitals_value)
                    else:
                        self.log(f"Invalid vitals data format for device {device_sn}")
                        return
                except json.JSONDecodeError:
                    self.log(f"Could not parse vitals data for device {device_sn}")
                    return

            rtv = vitals_from_dict(vitals_value)
            # print(f'rtv: {rtv}')
            metrics = self.analyzer.add_measurement(rtv)

            data = {
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                'device_sn': device_sn,
                'heart_rate': rtv.hr,
                'movement': rtv.mv,
                'oxygen': rtv.ox,
                'battery': rtv.bat,
                'stress_level': metrics.stress_level,
                'sleep_quality': metrics.sleep_quality,
                'breathing_status': metrics.breathing_status,
                'activity_level': metrics.activity_level,
                'overall_health': metrics.overall_health
            }

            # Guardar en CSV
            #save_to_csv(data)
            self.clear_screen()
            # log(f'Device: {device_sn} | Heart: {rtv.hr} | Oxigen: {rtv.ox} | Movement: {rtv.mv} | Battery: {rtv.bat}')
            # log(f'Full vitals values: {rtv.to_dict()}')
            print(f"""
                Estado del bebé:
                - Latidos: {rtv.hr}
                - Movimiento: {rtv.mv}
                - Oxigeno: {rtv.ox}
                - Nivel de bateria: {rtv.bat:.1f}%
                - Nivel de estrés: {metrics.stress_level:.1f}%
                - Calidad del sueño: {metrics.sleep_quality:.1f}%
                - Estado respiratorio: {metrics.breathing_status}
                - Nivel de actividad: {metrics.activity_level}
                - Salud general: {metrics.overall_health:.1f}%
                """)

        except Exception as e:
            print(f'exception: {format_exception(e)}')

    async def _get_access_token(self, mini_token: str) -> Dict[str, Any]:
        """Get access token from Ayla"""
        url = self.config.region_config[self.config.region]['url_signin']
        region_config = self.config.region_config[self.config.region]

        data = {
            "app_id": region_config['app_id'],
            "app_secret": region_config['app_secret'],
            "provider": "owl_id",
            "token": mini_token,
        }

        try:
            return await self._make_request('POST', url, json=data)
        except Exception as e:
            logger.error(f"Access token retrieval failed: {e}")
            raise OwletError("Failed to get access token") from e

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def _make_request(
        self,
        method: str,
        url: str,
        **kwargs
    ) -> ClientResponse:
        session = await self._get_session()
        async with session.request(method, url, **kwargs) as response:
            response.raise_for_status()
            return await response.json()

    async def _authenticate_firebase(self) -> str:
        """Authenticate against Firebase and get JWT token"""
        api_key = self.config.region_config[self.config.region]['apiKey']
        url = f'https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={api_key}'

        data = {
            'email': self.config.user,
            'password': self.config.password,
            'returnSecureToken': True
        }

        try:
            response = await self._make_request(
                'POST',
                url,
                json=data,
                headers=self.ANDROID_HEADERS
            )
            return response['idToken']
        except Exception as e:
            logger.error(f"Firebase authentication failed: {e}")
            raise OwletError("Failed to authenticate with Firebase") from e

    async def _get_mini_token(self, jwt: str) -> str:
        """Get mini token from Owlet data service"""
        url = self.config.region_config[self.config.region]['url_mini']
        try:
            response = await self._make_request(
                'GET',
                url,
                headers={'Authorization': jwt}
            )
            return response['mini_token']
        except Exception as e:
            logger.error(f"Mini token retrieval failed: {e}")
            raise OwletError("Failed to get mini token") from e

    async def login(self) -> None:
        """Main login flow implementation"""
        try:
            # Validate credentials
            if not self.config.user or not self.config.password:
                raise OwletError("Missing credentials")

            # Check if token is still valid
            if (self.config.auth_token and
                    self.config.expire_time > datetime.now().timestamp()):
                return

            logger.info("Starting login process")

            # Execute authentication flow
            jwt = await self._authenticate_firebase()
            mini_token = await self._get_mini_token(jwt)
            auth_response = await self._get_access_token(mini_token)

            # Update configuration with new tokens
            self.config.auth_token = auth_response['access_token']
            self.config.expire_time = (
                    datetime.now().timestamp() +
                    auth_response['expires_in'] - 60
            )
            self.config.add_headers({
                'Authorization': f'auth_token {self.config.auth_token}'
            })

            logger.info("Login successful")

        except Exception as e:
            logger.error(f"Login failed: {e}")
            raise OwletError(f"Login failed: {str(e)}") from e

    async def close(self):
        """Close the client session"""
        if self._session and not self._session.closed:
            await self._session.close()

