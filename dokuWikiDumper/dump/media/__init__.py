import re
import urllib.parse as urlparse

from bs4 import BeautifulSoup
from requests import Session

from dokuWikiScraper.utils.util import smkdir


def getFiles(url, ns='', session:Session=None):
    """ Return a list of media filenames of a wiki """
    files = set()
    ajax = urlparse.urljoin(url, 'lib/exe/ajax.php')
    medialist = BeautifulSoup(
        session.post(ajax, {
            'call': 'medialist',
            'ns': ns,
            'do': 'media'
        }).text, 'lxml')
    medians = BeautifulSoup(
        session.post(ajax, {
            'call': 'medians',
            'ns': ns,
            'do': 'media'
        }).text, 'lxml')
    imagelinks = medialist.findAll(
        'a',
        href=lambda x: x and re.findall(
            '[?&](media|image)=',
            x))
    for a in imagelinks:
        query = urlparse.parse_qs(urlparse.urlparse(a['href']).query)
        key = 'media' if 'media' in query else 'image'
        files.add(query[key][0])
    files = list(files)
    namespacelinks = medians.findAll('a', {'class': 'idx_dir', 'href': True})
    for a in namespacelinks:
        query = urlparse.parse_qs(urlparse.urlparse(a['href']).query)
        files += getFiles(url, query['ns'][0], session=session)
    print('Found %d files in namespace %s' % (len(files), ns or '(all)'))
    return files


def dumpMedia(url: str = '', dumpDir: str = '', session:Session=None):
    if not dumpDir:
        raise ValueError('dumpDir must be set')
    prefix = dumpDir
    smkdir(prefix + '/media')
    smkdir(prefix + '/media_attic')
    smkdir(prefix + '/media_meta')

    fetch = urlparse.urljoin(url, 'lib/exe/fetch.php')

    files = getFiles(url, session=session)
    for title in files:
        titleparts = title.split(':')
        for i in range(len(titleparts)):
            dir = "/".join(titleparts[:i])
            smkdir(prefix + '/media/' + dir)
        with open(prefix + '/media/' + title.replace(':', '/'), 'wb') as f:
            f.write(session.get(fetch, params={'media': title}).content)
        print('File %s' % title)
        # time.sleep(1.5)