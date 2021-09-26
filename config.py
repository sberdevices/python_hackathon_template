import pydantic


class Settings(pydantic.BaseSettings):
    KAFKA_SERVER: str
    SMART_APPS: list = ['weather', 'video', 'horo', 'games', 'news', 'realty', 'head', 'top', 'search', 'finance']
    USER_ID: str

    @property
    def IR_TO(self):
        return f'IR_in_{self.USER_ID}'

    @property
    def IR_FROM(self):
        return f'IR_out_{self.USER_ID}'


settings = Settings()
