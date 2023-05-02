import os
import re
import threading
import time
import urllib.parse as urlparse

from bs4 import BeautifulSoup
import requests

from dokuWikiDumper.utils.util import smkdirs, uopen
from dokuWikiDumper.utils.util import print_with_lock as print


sub_thread_error = None


def getFiles(url, ns: str = '',  dumpDir: str = '', session: requests.Session=None):
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
        }).text, os.environ.get('htmlparser'))
    medians = BeautifulSoup(
        session.post(ajax, {
            'call': 'medians',
            'ns': ns,
            'do': 'media'
        }).text, os.environ.get('htmlparser'))
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


def dumpMedia(base_url: str = '', dumpDir: str = '', session=None, threads: int = 1, ignore_errors: bool = False):
    if not dumpDir:
        raise ValueError('dumpDir must be set')

    smkdirs(dumpDir + '/media')
    # smkdirs(dumpDir + '/media_attic')
    # smkdirs(dumpDir + '/media_meta')

    fetch = urlparse.urljoin(base_url, 'lib/exe/fetch.php')

    files = getFiles(base_url, dumpDir=dumpDir, session=session)
    def try_download(*args, **kwargs):
        try:
            download(*args, **kwargs)
        except Exception as e:
            if not ignore_errors:
                global sub_thread_error
                sub_thread_error = e
                raise e
            print(threading.current_thread().name, 'Error in sub thread: (', e, ') ignored')
    index_of_title = -1
    for title in files:
        index_of_title += 1
        while threading.active_count() > threads:
            time.sleep(0.1)
        if sub_thread_error:
            raise sub_thread_error
        print('Media: (%d/%d): [[%s]] ...' % (index_of_title+1, len(files), title))

        def download(title, session: requests.Session):
            child_path = title.replace(':', '/')
            child_path = child_path.lstrip('/')
            child_path = '/'.join(child_path.split('/')[:-1])
            smkdirs(dumpDir + '/media/' + child_path)
            file = dumpDir + '/media/' + title.replace(':', '/')
            local_size = -1
            if os.path.exists(file):
                local_size = os.path.getsize(file)
            with session.get(fetch, params={'media': title},
                            stream=True, headers={'Referer': base_url}
                            ) as r:
                r.raise_for_status()

                if local_size == -1:  # file does not exist
                    to_download = True
                else:
                    remote_size = int(r.headers.get('Content-Length', -2))
                    if local_size == remote_size:  # file exists and is complete
                        print(threading.current_thread().name,
                              'File [[%s]] exists (%d bytes)' % (title, local_size))
                        to_download = False
                    elif remote_size == -2:
                        print(threading.current_thread().name,
                          'File [[%s]] cannot get remote size ("Content-Length" missing), ' % title +
                          'will re-download anyway')
                        to_download = True
                    else:
                        to_download = True  # file exists but is incomplete

                if to_download:
                    r.raw.decode_content = True
                    with open(file, 'wb') as f:
                        for chunk in r.iter_content(chunk_size=8192):
                            f.write(chunk)
                        print(threading.current_thread().name,
                              'File [[%s]] Done' % title)
                # modify mtime based on Last-Modified header
                last_modified = r.headers.get('Last-Modified', None)
                if last_modified:
                    mtime = time.mktime(time.strptime(
                        last_modified, '%a, %d %b %Y %H:%M:%S %Z'))
                    atime = os.stat(file).st_atime
                    # atime is not modified
                    os.utime(file, times=(atime, mtime))
                    # print(atime, mtime)

            # time.sleep(1.5)

        t = threading.Thread(target=try_download, daemon=True,
                             args=(title, session))
        t.start()

    while threading.active_count() > 1:
        time.sleep(2)
        print('Waiting for %d threads to finish' %
              (threading.active_count() - 1), end='\r')
