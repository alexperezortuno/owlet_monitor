# utils/config.py
import os
from datetime import time
from typing import Any

import requests


class Config:
    user: str
    password: str
    region: str = "world"
    log_level: str = "INFO"
    region_config: dict
    url_login: str
    auth_token: str = None
    expire_time: int = 0
    headers: dict = {}
    session: Any = requests.session()
    dsn: list = []
    url_props: list = []
    url_activate: list = []

    def __init__(self):
        self.user = os.getenv("OWLET_USER") if os.getenv("OWLET_USER") else input("Enter your username: ")
        self.password = os.getenv("OWLET_PASS") if os.getenv("OWLET_PASS") else input("Enter your password: ")
        self.region = os.getenv("OWLET_REGION") if os.getenv("OWLET_REGION") else "world"
        self.region_config = {
            'world': {
                'url_mini': 'https://ayla-sso.owletdata.com/mini/',
                'url_signin': 'https://user-field-1a2039d9.aylanetworks.com/api/v1/token_sign_in',
                'url_base': 'https://ads-field-1a2039d9.aylanetworks.com/apiv1',
                'apiKey': 'AIzaSyCsDZ8kWxQuLJAMVnmEhEkayH1TSxKXfGA',
                'app_id': 'sso-prod-3g-id',
                'app_secret': 'sso-prod-UEjtnPCtFfjdwIwxqnC0OipxRFU',
            },
            'europe': {
                'url_mini': 'https://ayla-sso.eu.owletdata.com/mini/',
                'url_signin': 'https://user-field-eu-1a2039d9.aylanetworks.com/api/v1/token_sign_in',
                'url_base': 'https://ads-field-eu-1a2039d9.aylanetworks.com/apiv1',
                'apiKey': 'AIzaSyDm6EhV70wudwN3iOSq3vTjtsdGjdFLuuM',
                'app_id': 'OwletCare-Android-EU-fw-id',
                'app_secret': 'OwletCare-Android-EU-JKupMPBoj_Npce_9a95Pc8Qo0Mw',
            }
        }
        self.url_login = 'https://www.googleapis.com'

    def get_region(self):
        return self.region

    def set_region(self, region):
        self.region = region

    def get_region_config(self):
        return self.region_config[self.region]

    def set_region_config(self, region_config):
        self.region_config = region_config

    def get_url_login(self):
        return self.url_login

    def get_token(self):
        return self.auth_token

    def set_token(self, token):
        self.auth_token = token

    def get_user(self):
        return self.user

    def get_password(self):
        return self.password

    def get_expire_time(self):
        return self.expire_time

    def set_expire_time(self, expire_time):
        self.expire_time = expire_time

    def is_time_expired(self):
        return self.expire_time < int(time.time())

    def get_headers(self):
        return self.headers

    def set_headers(self, headers):
        self.headers = headers

    def add_headers(self, header):
        self.headers.update(header)

    def set_session(self):
        self.session = requests.session()

    def get_session(self):
        return self.session

    def get_dsn(self):
        return self.dsn

    def set_dsn(self, dsn):
        self.dsn = dsn

    def append_dsn(self, dsn):
        self.dsn.append(dsn)

    def get_props(self):
        return self.url_props

    def set_props(self, props):
        self.url_props = props

    def append_props(self, props):
        self.url_props.append(props)

    def get_activate(self):
        return self.url_activate

    def set_activate(self, activate):
        self.url_activate = activate

    def append_activate(self, activate):
        self.url_activate.append(activate)
