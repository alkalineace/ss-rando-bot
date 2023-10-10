from racetime_bot import Bot

from .handler import RandoHandler
from .website import Website


class RandoBot(Bot):
    """
    RandoBot base class.
    """

    def __init__(self, ssr_api_key, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.website = Website(ssr_api_key)

    def get_handler_class(self):
        return RandoHandler

    def get_handler_kwargs(self, *args, **kwargs):
        return {
            **super().get_handler_kwargs(*args, **kwargs),
            'website': self.website
        }
