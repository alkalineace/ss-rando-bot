import json

import requests

class Website:
    preset_endpoint = 'https://ssrando.com/api/dynamicdata/racePresets'

    def __init__(self, ssr_api_key):
        self.ssr_api_key = ssr_api_key
        self.presets = self.load_presets()

    def load_presets(self):
        presets = requests.get(self.preset_endpoint).json()
        
        return {
            key: {
                'name': value['name'],
                'settings': value['settings']
            }
            for key, value in presets.items()
        }