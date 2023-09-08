from racetime_bot import Bot

from .handler import RandoHandler


class RandoBot(Bot):
    """
    RandoBot base class.
    """

    def __init__(self, *args, **kwargs):
        Bot.racetime_host = "localhost:8000"
        Bot.racetime_secure = False
        super().__init__(*args, **kwargs)

    def get_handler_class(self):
        return RandoHandler

    def get_handler_kwargs(self, *args, **kwargs):
        return {
            **super().get_handler_kwargs(*args, **kwargs)
        }
