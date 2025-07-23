from utils.config import Config


class Auth:
    def __init__(self):
        self.config = Config()


    async def login(self):
        url = f"{self.config.url_login}/identitytoolkit/v3/relyingparty/verifyPassword?key="

