import json
import os
import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

from dokuWikiDumper.utils.util import uopen

infoFilename = 'dumpMeta/info.json'
homepageFilename = 'dumpMeta/index.html'
iconFilename = 'dumpMeta/favicon.ico'


def get_info(dumpDir: str) -> dict:
    if os.path.exists(os.path.join(dumpDir, infoFilename)):
        with uopen(os.path.join(dumpDir, infoFilename), 'r') as f:
            _info = json.load(f)
            return _info

    return {}


def update_info_json(dumpDir: str, info: dict):
    '''Only updates given keys in info.'''
    _info = get_info(dumpDir)
    info = {**_info, **info}

    with uopen(os.path.join(dumpDir, infoFilename), 'w') as f:
        json.dump(info, f, indent=4, ensure_ascii=False)


def get_html_lang(html: str) -> Optional[str]:
    '''Returns the language of the html document.'''

    soup = BeautifulSoup(html, 'lxml')
    # <html lang="en" dir="ltr" class="no-js">
    lang = soup.html.get('lang')

    return lang


def get_wiki_name(html: str):
    '''Returns the name of the wiki.

    Tuple: (wiki_name: Optional[str], raw_title: Optional[str])'''

    soup = BeautifulSoup(html, 'lxml')
    raw_title = soup.head.title.text
    wiki_name = re.search(r'\[(.+)\]', raw_title)  # 'start [wikiname]'.
    if wiki_name:
        wiki_name = wiki_name.group(1)
    else:
        print('Warning: Could not find wiki name in HTML title.')

    return wiki_name, raw_title


def get_icon(html: str):
    '''Returns the icon url.'''

    soup = BeautifulSoup(html, 'lxml')
    icon_url = soup.find('link', rel='shortcut icon')
    if icon_url:
        icon_url = icon_url.get('href')
    else:
        print('Warning: Could not find icon in HTML.')

    return icon_url


def save_icon(dumpDir: str, url: str, session: requests.Session):
    if url is None:
        return False
    with open(os.path.join(dumpDir, iconFilename), 'wb') as f:
        f.write(session.get(url).content)
        return True


def update_info(dumpDir: str, doku_url: str, session: requests.Session):
    '''Saves the info of the wiki.'''
    html = session.get(doku_url).text
    with uopen(os.path.join(dumpDir, homepageFilename), 'w') as f:
        f.write(html)

    wiki_name, raw_title = get_wiki_name(html)
    lang = get_html_lang(html)
    icon_url = urljoin(doku_url, get_icon(html))
    save_icon(dumpDir=dumpDir, url=icon_url, session=session)

    info = {
        'wiki_name': wiki_name,
        'raw_title': raw_title,
        'doku_url': doku_url,
        'lang': lang,
        'icon_url': icon_url,
    }
    print('Info:', info)
    update_info_json(dumpDir, info)
