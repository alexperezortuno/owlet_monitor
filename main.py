import time

import requests

from api.client import OwletClient
from utils.config import Config

conf: Config | None = None

def load_settings() -> None:
    global conf
    conf = Config()

if __name__ == "__main__":
    load_settings()
    client = OwletClient(conf)
    conf.set_session()
    client.log('Login success')

    while True:
        try:
            client.login()
            client.fetch_dsn()
            for prop in client.fetch_props():
                 client.record_vitals(prop)
            time.sleep(10)
        except requests.exceptions.RequestException as e:
            client.log('Network error: %s' % e)
            time.sleep(1)
            conf.set_session()
        except KeyboardInterrupt:
            break
        except Exception as e:
            client.log(f'Exception:{e}')
    