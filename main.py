import asyncio
import os
import time

from api.client import OwletClient
from utils.config import Config

if 'TERM' not in os.environ:
    os.environ['TERM'] = 'xterm'


async def main() -> None:
    config = Config()
    client = OwletClient(config)
    try:
        await client.login()
        #client.fetch_dsn()
        await client.fetch_dsn_async()

        while True:
            for prop in client.fetch_props():
                client.record_vitals(prop)
            time.sleep(10)
    except KeyboardInterrupt:
        client.log('Exiting...')
    except Exception as e:
        client.log(f'Exception:{e}')
    finally:
        await client.close()


if __name__ == "__main__":
    asyncio.run(main())
    