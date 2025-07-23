import csv
import json
import os
import platform
import sys
import time
from datetime import datetime
from traceback import format_exception

import requests

from api.utils import vitals_from_dict, VitalsAnalyzer
from exceptions import OwletError
from utils.config import Config


class OwletClient:
    analyzer: VitalsAnalyzer | None = None

    def __init__(self, config: Config = None):
        self.conf = config
        self.analyzer = VitalsAnalyzer()

    def log(self, s) -> None:
        sys.stderr.write(s + '\n')
        sys.stderr.flush()

    def record(self, s) -> None:
        sys.stdout.write(s + '\n')
        sys.stdout.flush()

    def login(self) -> None:
        try:
            owlet_user, owlet_pass = self.conf.get_user(), self.conf.get_password()
            owlet_region = self.conf.get_region()
            if not len(owlet_user):
                raise OwletError("OWLET_USER is empty")
            if not len(owlet_pass):
                raise OwletError("OWLET_PASS is empty")
        except KeyError as e:
            raise OwletError("OWLET_USER or OWLET_PASS env var is not defined")

        if owlet_region is None:
            raise OwletError("OWLET_REGION env var '{}' not recognised - must be one of {}".format(
                owlet_region, self.conf.region_config.keys()))

        if self.conf.get_token() is not None and (self.conf.get_expire_time() > time.time()):
            return

        self.log('Logging in')
        # authenticate against Firebase, get the JWT.
        # need to pass the X-Android-Package and X-Android-Cert headers because
        # the API key is restricted to the Owlet Android app
        # https://cloud.google.com/docs/authentication/api-keys#api_key_restrictions
        api_key = self.conf.region_config[owlet_region]['apiKey']
        r = requests.post(f'https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={api_key}',
                          data=json.dumps({'email': owlet_user, 'password': owlet_pass, 'returnSecureToken': True}),
                          headers={
                              'X-Android-Package': 'com.owletcare.owletcare',
                              'X-Android-Cert': '2A3BC26DB0B8B0792DBE28E6FFDC2598F9B12B74'
                          })
        r.raise_for_status()
        jwt = r.json()['idToken']
        # authenticate against owletdata.com, get the mini_token
        r = requests.get(self.conf.region_config[owlet_region]
                         ['url_mini'], headers={'Authorization': jwt})
        r.raise_for_status()
        mini_token = r.json()['mini_token']
        # authenticate against Ayla, get the access_token
        r = requests.post(self.conf.region_config[owlet_region]['url_signin'], json={
            "app_id": self.conf.region_config[owlet_region]['app_id'],
            "app_secret": self.conf.region_config[owlet_region]['app_secret'],
            "provider": "owl_id",
            "token": mini_token,
        })
        r.raise_for_status()
        auth_token = r.json()['access_token']
        # we will re-auth 60 seconds before the token expires
        self.conf.set_expire_time(time.time() + r.json()['expires_in'] - 60)
        self.conf.add_headers({'Authorization': f'auth_token {auth_token}'})
        self.log('Auth token %s' % auth_token)

    def fetch_dsn(self):
        if len(self.conf.get_dsn()) == 0:
            self.log('Getting DSN')
            r = self.conf.get_session().get(self.conf.get_region_config().get('url_base') + '/devices.json',
                                            headers=self.conf.get_headers())
            r.raise_for_status()
            devs = r.json()
            if len(devs) < 1:
                raise OwletError('Found zero Owlet monitors')
            # Allow for multiple devices
            self.conf.set_dsn([])
            self.conf.set_props([])
            self.conf.set_activate([])
            for device in devs:
                device_sn = device['device']['dsn']
                self.conf.append_dsn(device_sn)
                self.log(f'Found Owlet monitor device serial number {device_sn}')
                self.conf.append_props(
                    f"{self.conf.get_region_config().get('url_base')}/dsns/{device_sn}/properties.json"
                )
                self.conf.append_activate(
                    f"{self.conf.get_region_config().get('url_base')}/dsns/{device_sn}/properties/APP_ACTIVE/datapoints.json"
                )

    def reactivate(self, url_activate):
        payload = {"datapoint": {"metadata": {}, "value": 1}}
        r = self.conf.get_session().post(url_activate,
                                         json=payload,
                                         headers=self.conf.get_headers())
        r.raise_for_status()

    def fetch_props(self):
        # Ayla cloud API data is updated only when APP_ACTIVE periodically reset to 1.
        my_props = []
        # Get properties for each device; note no pause between requests for each device
        for device_sn, next_url_activate, next_url_props in zip(self.conf.get_dsn(), self.conf.get_activate(),
                                                                self.conf.get_props()):
            self.reactivate(next_url_activate)
            device_props = {'DSN': device_sn}
            r = self.conf.get_session().get(next_url_props, headers=self.conf.get_headers())
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

    async def close(self):
        """Close the client session"""
        if self._session and not self._session.closed:
            await self._session.close()

