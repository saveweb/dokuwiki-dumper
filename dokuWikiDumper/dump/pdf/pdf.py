import copy
from dataclasses import dataclass
import os
import queue
import threading
from typing import Optional

import requests
from dokuWikiDumper.dump.content.revisions import get_revisions
from dokuWikiDumper.dump.content.titles import load_get_save_titles
from dokuWikiDumper.utils.util import smkdirs
from dokuWikiDumper.utils.util import print_with_lock as print

from dokuWikiDumper.exceptions import DispositionHeaderMissingError

PDF_DIR = 'pdf/'
PDF_PAGR_DIR = PDF_DIR + 'pages/'
PDF_OLDPAGE_DIR = PDF_DIR + 'attic/'

sub_thread_error = None


@dataclass
class DumpPDFParams:
    dump_dir: str
    title: str
    title_index: int
    doku_url: str
    session: requests.Session
    current_only: bool

def dump_PDF(doku_url, dump_dir,
                  session: requests.Session, threads: int = 1,
                  ignore_errors: bool = False, current_only: bool = False):
    titles = load_get_save_titles(dump_dir=dump_dir, url=doku_url, session=session)
    
    if not len(titles):
        print('Empty wiki')
        return False
    
    tasks_queue: queue.Queue[Optional[DumpPDFParams]] = queue.Queue(maxsize=threads)

    workers: list[threading.Thread] = []
    # spawn workers
    for i in range(threads):
        t = threading.Thread(name=f"worker-{i}", target=dump_pdf_worker, args=(tasks_queue, ignore_errors))
        t.daemon = True
        t.start()
        workers.append(t)

    task_templ = DumpPDFParams(dump_dir=dump_dir, doku_url=doku_url, session=session, current_only=current_only,
                              title_index=-999, title="dokuwikidumper_placehold")

    for index, title in enumerate(titles):
        if sub_thread_error:
            raise sub_thread_error

        task = copy.copy(task_templ)
        task.title_index = index
        task.title = title
        tasks_queue.put(task)
        print('PDF: (%d/%d): [[%s]] ...' % (index+1, len(titles), title))

    for _ in range(threads):
        tasks_queue.put(None)

    tasks_queue.join()

    for w in workers:
        w.join()
        print('worker %s finished' % w.name)

    if sub_thread_error:
        raise sub_thread_error


def dump_pdf_worker(tasks_queue: queue.Queue[Optional[DumpPDFParams]], ignore_errors: bool):
    global sub_thread_error
    while task := tasks_queue.get():
        try:
            dump_pdf_page(task)
        except Exception as e:
            if not ignore_errors:
                sub_thread_error = e
                raise e
            else:
                print('[',task.title_index+1,'] Error in sub thread: (', e, ') ignored')
        finally:
            tasks_queue.task_done()
    tasks_queue.task_done()


def dump_pdf_page(task: DumpPDFParams):
    msg_header = '['+str(task.title_index + 1)+']: '

    file = task.dump_dir + '/' + PDF_PAGR_DIR + task.title.replace(':', '/') + '.pdf'
    local_size = -1
    if os.path.isfile(file):
        local_size = os.path.getsize(file)
    with task.session.get(task.doku_url, params={'do': 'export_pdf', 'id': task.title}, stream=True) as r:
        r.raise_for_status()
        if 'Content-Disposition' not in r.headers:
            raise DispositionHeaderMissingError(r)
        remote_size = r.headers.get('Content-Length', -2)

        if local_size == remote_size:
            print(msg_header, '[[%s]]' % task.title, 'already exists')
        else:
            child_path = task.title.replace(':', '/')
            child_dir = os.path.dirname(child_path)
            smkdirs(task.dump_dir, PDF_PAGR_DIR, child_dir)
            with open(file, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(msg_header, '[[%s]]' % task.title, 'saved')

    if task.current_only:
        return True

    revs = get_revisions(doku_url=task.doku_url, session=task.session, title=task.title, msg_header=msg_header)

    for rev in revs[1:]:
        if 'id' in rev and rev['id']:
            try:
                r = task.session.get(task.doku_url, params={'do': 'export_pdf', 'id': task.title, 'rev': rev['id']})
                r.raise_for_status()
                content = r.content
                smkdirs(task.dump_dir, PDF_OLDPAGE_DIR, child_dir)
                old_pdf_path = task.dump_dir + '/' + PDF_OLDPAGE_DIR + child_path + '.' + rev['id'] + '.pdf'

                with open(old_pdf_path, 'bw') as f:
                    f.write(content)
                print(msg_header, '    Revision %s of [[%s]] saved.' % (rev['id'], task.title))
            except requests.HTTPError as e:
                print(msg_header, '    Revision %s of [[%s]] failed: %s' % (rev['id'], task.title, e))