import os
import re
import threading
import time
import urllib.parse as urlparse

from bs4 import BeautifulSoup

from dokuWikiDumper.utils.util import smkdirs, uopen
from dokuWikiDumper.utils.util import print_with_lock as print


def getFiles(url, ns: str = '',  dumpDir: str = '', session=None):
    """ Return a list of media filenames of a wiki """

    if dumpDir and os.path.exists(dumpDir + '/dumpMeta/files.txt'):
        with uopen(dumpDir + '/dumpMeta/files.txt', 'r') as f:
            files = f.read().splitlines()
            if files[-1] == '--END--':
                print('Loaded %d files from %s' %
                      (len(files) - 1, dumpDir + '/dumpMeta/files.txt'))
                return files[:-1]  # remove '--END--'

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

    if dumpDir:
        smkdirs(dumpDir + '/dumpMeta')
        with uopen(dumpDir + '/dumpMeta/files.txt', 'w') as f:
            f.write('\n'.join(files))
            f.write('\n--END--\n')

    return files


def dumpMedia(url: str = '', dumpDir: str = '', session=None, threads: int = 1):
    if not dumpDir:
        raise ValueError('dumpDir must be set')

    smkdirs(dumpDir + '/media')
    # smkdirs(dumpDir + '/media_attic')
    # smkdirs(dumpDir + '/media_meta')

    fetch = urlparse.urljoin(url, 'lib/exe/fetch.php')

    files = getFiles(url, dumpDir=dumpDir, session=session)
    for title in files:
        while threading.active_count() > threads:
            time.sleep(0.1)

        def download(title, session):
            child_path = title.replace(':', '/')
            child_path = child_path.lstrip('/')
            child_path = '/'.join(child_path.split('/')[:-1])
            smkdirs(dumpDir + '/media/' + child_path)

            with open(dumpDir + '/media/' + title.replace(':', '/'), 'wb') as f:
                # open in binary mode
                f.write(session.get(fetch, params={'media': title}).content)
            print(threading.current_thread().name, 'File [[%s]] Done' % title)
            # time.sleep(1.5)
        t = threading.Thread(target=download, daemon=True,
                             args=(title, session))
        t.start()

    while threading.active_count() > 1:
        time.sleep(2)
        print('Waiting for %d threads to finish' %
              (threading.active_count() - 1), end='\r')
