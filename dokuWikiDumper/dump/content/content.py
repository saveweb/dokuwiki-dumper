import copy
from dataclasses import dataclass
import queue
import time
import threading
from typing import Callable, Optional

from requests import Session

from dokuWikiDumper.exceptions import ActionEditDisabled, ActionEditTextareaNotFound, DispositionHeaderMissingError

from .revisions import get_revisions, get_source_edit, get_source_export, save_page_changes
from .titles import load_get_save_titles
from dokuWikiDumper.utils.util import smkdirs, uopen
from dokuWikiDumper.utils.util import print_with_lock as print

sub_thread_error = None


@dataclass
class DumpPageParams:
    dump_dir: str
    get_source: Callable
    title_index: int
    title: str
    doku_url: str
    session: Session
    current_only: bool




def dump_content(*, doku_url: str, dump_dir: str, session: Session, threads: int = 1,
                 ignore_errors: bool = False, ignore_action_disabled_edit: bool = False, current_only: bool = False):
    titles = load_get_save_titles(dump_dir=dump_dir, url=doku_url, session=session)

    if not len(titles):
        print('Empty wiki')
        return False

    r1 = session.get(doku_url, params={'id': titles[0], 'do': 'export_raw'})

    get_source = get_source_export
    if 'html' in r1.headers['content-type']:
        print('\nWarning: export_raw action not available, using edit action\n')
        time.sleep(3)
        get_source = get_source_edit


    tasks_queue: queue.Queue[Optional[DumpPageParams]] = queue.Queue(maxsize=threads)

    workers: list[threading.Thread] = []
    # spawn workers
    for i in range(threads):
        t = threading.Thread(name=f"worker-{i}", target=dump_worker, args=(tasks_queue, ignore_errors, ignore_action_disabled_edit))
        t.daemon = True
        t.start()
        workers.append(t)

    task_templ = DumpPageParams(dump_dir=dump_dir, doku_url=doku_url, session=session, get_source=get_source, current_only=current_only,
                          title_index=-999, title="dokuwikidumper_placehold")

    for index, title in enumerate(titles):
        if sub_thread_error:
            raise sub_thread_error

        task = copy.copy(task_templ)
        task.title_index = index
        task.title = title
        tasks_queue.put(task)
        print('Content: (%d/%d): [[%s]] ...' % (index+1, len(titles), title))

    for _ in range(threads):
        tasks_queue.put(None)

    tasks_queue.join()

    for w in workers:
        w.join()
        print('worker %s finished' % w.name)

    if sub_thread_error:
        raise sub_thread_error


def dump_worker(tasks_queue: queue.Queue[Optional[DumpPageParams]], ignore_errors: bool, ignore_action_disabled_edit: bool):
    global sub_thread_error
    while task := tasks_queue.get():
        try:
            dump_page(task)
        except Exception as e:
            if isinstance(e, ActionEditDisabled) and ignore_action_disabled_edit:
                print('[',task.title_index,'] action disabled: edit. ignored')
            elif isinstance(e, ActionEditTextareaNotFound) and ignore_action_disabled_edit:
                print('[',task.title_index,'] action edit: textarea not found. ignored')
            elif not ignore_errors:
                sub_thread_error = e
                raise e
            else:
                print('[',task.title_index,'] Error in sub thread: (', e, ') ignored')
        finally:
            tasks_queue.task_done()
    tasks_queue.task_done()


def dump_page(task: DumpPageParams):
    source = task.get_source(task.doku_url, task.title, session=task.session)
    msg_header = '['+str(task.title_index + 1)+']: '
    child_path = task.title.replace(':', '/')
    child_path = child_path.lstrip('/')
    child_path = '/'.join(child_path.split('/')[:-1])

    smkdirs(task.dump_dir, '/pages/' + child_path)
    with uopen(task.dump_dir + '/pages/' + task.title.replace(':', '/') + '.txt', 'w') as f:
        f.write(source)

    if task.current_only:
        print(msg_header, '    [[%s]] saved.' % (task.title))
        return

    revs = get_revisions(task.doku_url, task.title, session=task.session, msg_header=msg_header)


    save_page_changes(dumpDir=task.dump_dir, child_path=child_path, title=task.title, 
                       revs=revs, msg_header=msg_header)

    for rev in revs[1:]:
        if 'id' in rev and rev['id']:
            try:
                txt = task.get_source(task.doku_url, task.title, rev['id'], session=task.session)
                smkdirs(task.dump_dir, '/attic/' + child_path)
                with uopen(task.dump_dir + '/attic/' + task.title.replace(':', '/') + '.' + rev['id'] + '.txt', 'w') as f:
                    f.write(txt)
                print(msg_header, '    Revision %s of [[%s]] saved.' % (
                    rev['id'], task.title))
            except DispositionHeaderMissingError:
                print(msg_header, '    Revision %s of [[%s]] is empty. (probably deleted)' % (
                    rev['id'], task.title))
        else:
            print(msg_header, '    Revision %s of [[%s]] failed: %s' % (rev['id'], task.title, 'Rev id not found (please check ?do=revisions of this page)'))
