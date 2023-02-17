import os
import re
import sys
import time
from urllib.parse import urlparse

import requests


def avoidSites(url: str = ''):
    site = urlparse(url).netloc
    avoidList = ['www.dokuwiki.org'] # TODO: Add more sites
    if site in avoidList:
        if input('\nWarning:\nYou are trying to dump '+site+', which is in the avoid list. \n'+
        'If you just want to test '+
        'if this program can dump dokuwiki successfully, please DO NOT do this, '+
        '\nthis will bring a lot of pressure to the server of '+ site +
        '\n\nContinue anyway? (y/n): ') != 'y':
            sys.exit(1)

        print('You have been warned. :-)')
        time.sleep(3)

def smkdir(dir: str = '') -> bool:
    """ safe mkdir, return: True->created, False->existed """
    if not os.path.exists(dir):
        os.mkdir(dir)
        return True

    return False

def standardizeUrl(url: str = ''):
    """ Add http:// if not present """
    if not url.startswith('http'):
        url = 'http://' + url
    return url

def getDokuUrl(url: str = '', session=requests.Session()):
    r = session.get(url)
    dokuUrl = r.url

    return dokuUrl

def buildBaseUrl(url: str = '') -> str:
    r = urlparse(url)
    path = r.path
    if path and path != '/' and not path.endswith('/'):
        path = path[:path.rfind('/')]
    baseUrl = r.scheme + '://' + r.netloc + path
    if not baseUrl.endswith('/'):
        baseUrl += '/'

    return baseUrl

def url2prefix(url):
    """Convert URL to a valid prefix filename."""

    # At this point, both api and index are supposed to be defined

    # use request to transform prefix into a valid filename

    r = urlparse(url)
    # prefix = r.netloc + r.path
    if r.path and r.path != '/' and not r.path.endswith('/'):
        # truncate to last slash
        prefix = r.netloc + r.path[:r.path.rfind('/')]
    else:
        prefix = r.netloc + r.path
    prefix = prefix.lower()
    prefix = re.sub(r"(/[a-z0-9]+\.php)", "", prefix)
    prefix = prefix.strip('/')
    prefix = re.sub(r"/", "_", prefix)

    # domain = re.sub(r"\.", "", domain)
    # domain = re.sub(r"[^A-Za-z0-9]", "_", domain)

    return prefix

def loadTitles(titlesFilePath) -> list[str]|None:
    """ Load titles from dump directory

    Return:
        `list[str]`: titles
        `None`: titles file does not exist or incomplete
     """
    if os.path.exists(titlesFilePath):
        with uopen(titlesFilePath, 'r') as f:
            titles = f.read().splitlines()
        if len(titles) and titles[-1] == '--END--':
            print('Loaded %d titles from %s' % (len(titles) - 1, titlesFilePath))
            return titles[:-1]

    return None


def uopen(*args, **kwargs):
    """ I dont wanna type `encoding=utf8` anymore.
    Made for Windows compatibility :-( """
    return open(*args, encoding='UTF-8', **kwargs)
