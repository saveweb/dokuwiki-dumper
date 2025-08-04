import copy
from dataclasses import dataclass
import os
import queue
import re
import threading
import time
import urllib.parse as urlparse
from typing import Optional

from bs4 import BeautifulSoup
import requests

from dokuWikiDumper.utils.util import smkdirs, uopen
from dokuWikiDumper.utils.util import print_with_lock as print
from dokuWikiDumper.utils.config import runtime_config

sub_thread_error = None

@dataclass
class DumpMediaParams:
    dump_dir: str
    title: str
    title_index: int
    base_url: str
    session: requests.Session
    fetch_url: str


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
        }).text, runtime_config.html_parser)
    medians = BeautifulSoup(
        session.post(ajax, {
            'call': 'medians',
            'ns': ns,
            'do': 'media'
        }).text, runtime_config.html_parser)
    imagelinks = medialist.find_all(
        'a',
        href=lambda x: x and re.findall(
            '[?&](media|image)=',
            x))
    for a in imagelinks:
        query = urlparse.parse_qs(urlparse.urlparse(a['href']).query)
        key = 'media' if 'media' in query else 'image'
        files.add(query[key][0])
    files = list(files)
    namespacelinks = medians.find_all('a', {'class': 'idx_dir', 'href': True})
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


def dump_media(*, base_url: str, dumpDir: str, session: requests.Session, threads: int = 1, ignore_errors: bool = False):

    smkdirs(dumpDir + '/media')

    fetch = urlparse.urljoin(base_url, 'lib/exe/fetch.php')
    # media_repo = urlparse.urljoin(base_url, '_media')

    files = getFiles(base_url, dumpDir=dumpDir, session=session)

    tasks_queue: queue.Queue[Optional[DumpMediaParams]] = queue.Queue(maxsize=threads)

    workers: list[threading.Thread] = []
    # spawn workers
    for i in range(threads):
        t = threading.Thread(name=f"worker-{i}", target=dump_media_worker, args=(tasks_queue, ignore_errors))
        t.daemon = True
        t.start()
        workers.append(t)

    task_templ = DumpMediaParams(dump_dir=dumpDir, base_url=base_url, session=session, fetch_url=fetch,
                                title_index=-999, title="dokuwikidumper_placehold")

    for index, title in enumerate(files):
        if sub_thread_error:
            raise sub_thread_error

        task = copy.copy(task_templ)
        task.title_index = index
        task.title = title
        tasks_queue.put(task)
        print('Media: (%d/%d): [[%s]] ...' % (index+1, len(files), title))

    for _ in range(threads):
        tasks_queue.put(None)

    tasks_queue.join()

    for w in workers:
        w.join()
        print('worker %s finished' % w.name)

    if sub_thread_error:
        raise sub_thread_error


def dump_media_worker(tasks_queue: queue.Queue[Optional[DumpMediaParams]], ignore_errors: bool):
    global sub_thread_error
    while task := tasks_queue.get():
        try:
            download_media_file(task)
        except Exception as e:
            if not ignore_errors:
                sub_thread_error = e
                raise e
            else:
                print('[',task.title_index,'] Error in sub thread: (', e, ') ignored')
        finally:
            tasks_queue.task_done()
    tasks_queue.task_done()


def download_media_file(task: DumpMediaParams):
    child_path = task.title.replace(':', '/')
    child_path = child_path.lstrip('/')
    child_path = '/'.join(child_path.split('/')[:-1])
    smkdirs(task.dump_dir + '/media/' + child_path)
    file = task.dump_dir + '/media/' + task.title.replace(':', '/')
    local_size = -1
    if os.path.exists(file):
        local_size = os.path.getsize(file)
    with task.session.get(task.fetch_url, params={'media': task.title},
                    stream=True, headers={'Referer': task.base_url}
                    ) as r:
        r.raise_for_status()

        if local_size == -1:  # file does not exist
            to_download = True
        else:
            remote_size = int(r.headers.get('Content-Length', -2))
            if local_size == remote_size:  # file exists and is complete
                print('[%d] File [[%s]] exists (%d bytes)' % (task.title_index+1, task.title, local_size))
                to_download = False
            elif remote_size == -2:
                print('[%d] File [[%s]] cannot get remote size ("Content-Length" missing), ' % (task.title_index+1, task.title) +
                      'will re-download anyway')
                to_download = True
            else:
                to_download = True  # file exists but is incomplete

        if to_download:
            with open(file, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
                print('[%d] File [[%s]] Done' % (task.title_index+1, task.title))
        else:
            r.close()

        # modify mtime based on Last-Modified header
        last_modified = r.headers.get('Last-Modified', None)
        if last_modified:
            mtime = time.mktime(time.strptime(
                last_modified, '%a, %d %b %Y %H:%M:%S %Z'))
            atime = os.stat(file).st_atime
            # atime is not modified
            os.utime(file, times=(atime, mtime))
