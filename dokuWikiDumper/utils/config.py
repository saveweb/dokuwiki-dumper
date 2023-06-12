import datetime
import json
import os
from dataclasses import dataclass

from dokuWikiDumper.utils.util import Singleton, print_with_lock as print
from dokuWikiDumper.utils.util import uopen

CONFIG_FILEPATH = 'dumpMeta/config.json'


def update_config(dumpDir: str, config: dict):
    '''Only updates given keys in config.'''
    _config = get_config(dumpDir)
    config = {**_config, **config}
    print("Config: ", config)

    with uopen(os.path.join(dumpDir, CONFIG_FILEPATH), 'w') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)


def get_config(dumpDir: str) -> dict:
    if os.path.exists(os.path.join(dumpDir, CONFIG_FILEPATH)):
        with uopen(os.path.join(dumpDir, CONFIG_FILEPATH), 'r') as f:
            _config = json.load(f)
            return _config

    return {}


@dataclass
class _Dumper_running_config(metaclass = Singleton):
    html_parser: str = 'lxml'
    export_xhtml_action: str = 'export_xhtml' # 'export_xhtml' or 'export_raw'
running_config = _Dumper_running_config()