import json
import os
import sys
import time
import requests

from exceptions import OwletError
from utils.config import Config


class OwletClient:
    def __init__(self, config: Config = None):
        self.conf = config

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

    def record_vitals(self, p):
        device_sn = p['DSN']
        charge_status = p['CHARGE_STATUS']['value']
        base_station_on = p['BASE_STATION_ON']['value']
        heart = "%d" % p['HEART_RATE']['value']
        oxy = "%d" % p['OXYGEN_LEVEL']['value']
        mov = "wiggling" if p['MOVEMENT']['value'] else "still"
        disp = "%d, " % time.time()
        if charge_status >= 1:
            disp += "sock charging (%d)" % charge_status
            # base_station_on is (always?) 1 in this case
        elif charge_status == 0:
            if base_station_on == 0:
                # sock was unplugged, but user did not turn on the base station.
                # heart and oxygen levels appear to be reported, but we can't
                # yet assume the sock was placed on the baby's foot.
                disp += "sock not charging, base station off"
            elif base_station_on == 1:
                # base station was intentionally turned on, the sock is presumably
                # on the baby's foot, so we can trust heart and oxygen levels
                disp += heart + ", " + oxy + ", " + mov + ", " + device_sn
                self.record(disp)
            else:
                raise OwletError("Unexpected base_station_on=%d" % base_station_on)
        self.log("%s Status: " % device_sn + disp)
