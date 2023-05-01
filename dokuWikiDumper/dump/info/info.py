import json
import os
import re
from typing import Optional
from urllib.parse import urljoin

from bs4 import BeautifulSoup
import requests

from dokuWikiDumper.utils.util import print_with_lock as print
from dokuWikiDumper.utils.util import uopen

INFO_FILEPATH = 'dumpMeta/info.json'
HOMEPAGE_FILEPATH = 'dumpMeta/index.html'
CHECKPAGE_FILEPATH = 'dumpMeta/check.html'
ICON_FILEPATH = 'dumpMeta/favicon.ico'

# info.json keys
INFO_WIKI_NAME = "wiki_name"
INFO_RAW_TITLE = "raw_title"
INFO_DOKU_URL = "doku_url"
INFO_LANG = "language"
INFO_ICON_URL = "icon_url"

def get_info(dumpDir: str) -> dict:
    if os.path.exists(os.path.join(dumpDir, INFO_FILEPATH)):
        with uopen(os.path.join(dumpDir, INFO_FILEPATH), 'r') as f:
            _info = json.load(f)
            return _info

    return {}


def update_info_json(dumpDir: str, info: dict):
    '''Only updates given keys in info.'''
    _info = get_info(dumpDir)
    info = {**_info, **info}

    with uopen(os.path.join(dumpDir, INFO_FILEPATH), 'w') as f:
        json.dump(info, f, indent=4, ensure_ascii=False)


def get_html_lang(html: str) -> Optional[str]:
    '''Returns the language of the html document.'''

    soup = BeautifulSoup(html, os.environ.get('htmlparser'))
    # <html lang="en" dir="ltr" class="no-js">
    lang = soup.html.get('lang')

    return lang


def get_wiki_name(html: str):
    '''Returns the name of the wiki.

    Tuple: (wiki_name: Optional[str], raw_title: Optional[str])'''

    soup = BeautifulSoup(html, os.environ.get('htmlparser'))
    raw_title = soup.head.title.text
    wiki_name = re.search(r'\[(.+)\]', raw_title)  # 'start [wikiname]'.
    if wiki_name:
        wiki_name = wiki_name.group(1)
    else:
        print('Warning: Could not find wiki name in HTML title.')

    return wiki_name, raw_title


def get_icon(html: str):
    '''Returns the icon url.'''

    soup = BeautifulSoup(html, os.environ.get('htmlparser'))
    icon_url = soup.find('link', rel='shortcut icon')
    if icon_url:
        icon_url = icon_url.get('href')
    else:
        print('Warning: Could not find icon in HTML.')

    return icon_url


def save_icon(dumpDir: str, url: str, session: requests.Session):
    if url is None:
        return False
    r = session.get(url)
    if 'image' not in r.headers.get('content-type', ''):
        print('Warning: Icon is not an image.')
        return False

    with open(os.path.join(dumpDir, ICON_FILEPATH), 'wb') as f:
        f.write(r.content)
        return True



def update_info(dumpDir: str, doku_url: str, session: requests.Session):
    '''Saves the info of the wiki.'''
    homepage_html = session.get(doku_url).text
    with uopen(os.path.join(dumpDir, HOMEPAGE_FILEPATH), 'w') as f:
        f.write(homepage_html)
        print('Saved homepage to', HOMEPAGE_FILEPATH)

    checkpage_html = session.get(doku_url, params={'do': 'check'}).text
    with uopen(os.path.join(dumpDir, CHECKPAGE_FILEPATH), 'w') as f:
        f.write(checkpage_html)
        print('Saved checkpage to', CHECKPAGE_FILEPATH)

    wiki_name, raw_title = get_wiki_name(homepage_html)
    lang = get_html_lang(homepage_html)
    icon_url = urljoin(doku_url, get_icon(homepage_html))
    save_icon(dumpDir=dumpDir, url=icon_url, session=session)

    info = {
        INFO_WIKI_NAME: wiki_name,
        INFO_RAW_TITLE: raw_title,
        INFO_DOKU_URL: doku_url,
        INFO_LANG: lang,
        INFO_ICON_URL: icon_url,
    }
    print('Info:', info)
    update_info_json(dumpDir, info)
