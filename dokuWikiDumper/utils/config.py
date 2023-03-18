import datetime
import json
import os

from dokuWikiDumper.utils.util import uopen

configPath = 'dumpMeta/config.json'


def update_config(dumpDir: str, config: dict):
    '''Only updates given keys in config.'''
    _config = get_config(dumpDir)
    config = {**_config, **config}
    print("Config: ", config)

    with uopen(os.path.join(dumpDir, configPath), 'w') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def get_config(dumpDir: str) -> dict:
    if os.path.exists(os.path.join(dumpDir, configPath)):
        with uopen(os.path.join(dumpDir, configPath), 'r') as f:
            _config = json.load(f)
            return _config

    return {}
