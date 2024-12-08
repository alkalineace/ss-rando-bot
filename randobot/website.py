import json

import requests

class Website:
    preset_endpoint = 'https://ssrando.com/api/dynamicdata/racePresets'
    github_endpoint = 'https://api.github.com/repos/ssrando/ssrando/releases'
    sha_endpoint = 'https://api.github.com/repos/ssrando/ssrando/git/ref/tags/'

    def __init__(self):
        self.load_presets()
        self.versions = self.load_versions()

    def load_presets(self):
        presets = requests.get(self.preset_endpoint).json()

        bit_preset_list = {}
        nobit_preset_list = {}

        try:
            for array_preset in presets:
                if array_preset['data'].get('bit') is None:
                    nobit_preset_list[array_preset["data"]["settings"]] = array_preset["data"]["name"]
                else:
                    bit_preset_list[array_preset["data"]["settings"]] = array_preset["data"]["name"]
        except:
            nobit_preset_list["kV3MJkABAAAAAAAAgEBAA0QBfAKnAABv5v8f+wEAAP//AwAAAAAAAMAQAAAAAAAAAAAAAMAPAAAAAAA2QIEIDgAQgACA8AcgAkigfDo="] = "No-bit Season 3"
            bit_preset_list["kV3MJkABAAAAAAAAgEFAA0QBfAKnAABv5v8f+wEAAP//AwAAAAAAAMAQAAAAAAAAAAAAAMAPAAAAAAA2QIEIDgAQgACA8AcgAkigfDo="] = "Season 3"

        self.bit_presets = bit_preset_list
        self.nobit_presets = nobit_preset_list
    
    def load_versions(self):
        params = {'per_page': 5, 'page': 1}
        versions = requests.get(self.github_endpoint, params=params).json()

        tags = []
        version_list = {}
        version_list["2.2.0_bd9ed41"] = "Season 3 (2.2.0_bd9ed41)"
        version_list["2.2.0_71349dd"] = "Remlits Tournament (2.2.0_71349dd)"
        version_list["2.2.0_20748a9"] = "Latest main (2.2.0_20748a9)"

        try:
            for array_version in versions:
                tags.append(array_version['tag_name'])
        except:
            return version_list

        for tag in tags:
            hashes = requests.get(self.sha_endpoint + tag).json()

            if tag[0] != 'v':
                tag = "v" + tag

            try:
                version = tag[1:] + "_" + hashes['object']['sha'][:7]
            except:
                return version_list

            if version_list != {}:
                version_list[version] = version
            else:
                version_list[version] = "Latest (" + version + ")"

        return version_list
    
    def reload_presets(self):
        print("trying to reload presets")
        temp = self.load_presets()

        if temp is not {}:
            print("successfully recovered presets")
            self.presets = temp