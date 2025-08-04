import copy
from dataclasses import dataclass
import os
import queue
import threading
import time
from typing import Optional
import requests
from dokuWikiDumper.dump.content.revisions import get_revisions, save_page_changes
from dokuWikiDumper.dump.content.titles import load_get_save_titles

from dokuWikiDumper.utils.util import smkdirs, uopen
from dokuWikiDumper.utils.util import print_with_lock as print
from dokuWikiDumper.utils.config import runtime_config

HTML_DIR = 'html/'
HTML_PAGR_DIR = HTML_DIR + 'pages/'
HTML_OLDPAGE_DIR = HTML_DIR + 'attic/'

sub_thread_error = None

@dataclass
class DumpHTMLParams:
    dump_dir: str
    title_index: int
    title: str
    doku_url: str
    session: requests.Session
    current_only: bool

def dump_HTML(doku_url, dump_dir,
                session: requests.Session, threads: int = 1,
                ignore_errors: bool = False, current_only: bool = False):
    smkdirs(dump_dir, HTML_PAGR_DIR)

    titles = load_get_save_titles(dump_dir=dump_dir, url=doku_url, session=session)
    
    if not len(titles):
        print('Empty wiki')
        return False
    
    tasks_queue: queue.Queue[Optional[DumpHTMLParams]] = queue.Queue(maxsize=threads)
    workers: list[threading.Thread] = []

    for i in range(threads):
        t = threading.Thread(name=f"worker-{i}", target=html_worker, args=(tasks_queue, ignore_errors))
        t.daemon = True
        t.start()
        workers.append(t)

    task_templ = DumpHTMLParams(dump_dir=dump_dir, title_index=0, title='', doku_url=doku_url, session=session, current_only=current_only)

    for index, title in enumerate(titles):
        if sub_thread_error:
            raise sub_thread_error

        task = copy.copy(task_templ)
        task.title_index, task.title = index, title
        tasks_queue.put(task)
        print('HTML: (%d/%d): [[%s]] ...' % (index+1, len(titles), title))

    for _ in range(threads):
        tasks_queue.put(None)

    tasks_queue.join()

    for w in workers:
        w.join()
        print('worker %s finished' % w.name)

    if sub_thread_error:
        raise sub_thread_error
def html_worker(tasks_queue: queue.Queue, ignore_errors: bool):
    while task := tasks_queue.get():
        try:
            dump_html_page(task)
        except Exception as e:
            if not ignore_errors:
                global sub_thread_error
                sub_thread_error = e
                raise e
            print('[',task.title_index+1,']Error in sub thread: (', e, ') ignored')
        finally:
            tasks_queue.task_done()
    tasks_queue.task_done()

def dump_html_page(task: DumpHTMLParams):
    r = task.session.get(task.doku_url, params={'do': runtime_config.export_xhtml_action, 'id': task.title})
    # export_html is a alias of export_xhtml, but not exist in older versions of dokuwiki
    r.raise_for_status()
    if r.text is None or r.text == '':
        raise Exception('Empty response (r.text)')

    msg_header = '['+str(task.title_index + 1)+']: '

    title2path = task.title.replace(':', '/')
    child_path = os.path.dirname(title2path)
    html_path = task.dump_dir + '/' + HTML_PAGR_DIR + title2path + '.html'
    smkdirs(task.dump_dir, HTML_PAGR_DIR, child_path)
    with uopen(html_path, 'w') as f:
        f.write(r.text)
        print(msg_header, '[[%s]]' % task.title, 'saved')

    if task.current_only:
        return True

    revs = get_revisions(doku_url=task.doku_url, session=task.session, title=task.title, msg_header=msg_header)

    for rev in revs[1:]:
        if 'id' in rev and rev['id']:
            try:
                r = task.session.get(task.doku_url, params={'do': runtime_config.export_xhtml_action, 'id': task.title, 'rev': rev['id']})
                r.raise_for_status()
                if r.text is None or r.text == '':
                    raise Exception('Empty response (r.text)')
                smkdirs(task.dump_dir, HTML_OLDPAGE_DIR, child_path)
                old_html_path = task.dump_dir + '/' + HTML_OLDPAGE_DIR + title2path + '.' + rev['id'] + '.html'

                with uopen(old_html_path, 'w') as f:
                    f.write(r.text)
                print(msg_header, '    Revision %s of [[%s]] saved.' % (rev['id'], task.title))
            except requests.HTTPError as e:
                print(msg_header, '    Revision %s of [[%s]] failed: %s' % (rev['id'], task.title, e))
        else:
            print(msg_header, '    Revision %s of [[%s]] failed: %s' % (rev['id'], task.title, 'Rev id not found (please check ?do=revisions of this page)'))

    save_page_changes(dumpDir=task.dump_dir, child_path=child_path, title=task.title, 
                       revs=revs, msg_header=msg_header)