import copy
from dataclasses import dataclass
import queue
import time
import threading
from typing import Callable
import concurrent.futures

from requests import Session

from dokuWikiDumper.exceptions import ActionEditDisabled, ActionEditTextareaNotFound, DispositionHeaderMissingError

from .revisions import get_revisions, get_source_edit, get_source_export, save_page_changes
from .titles import load_get_save_titles
from dokuWikiDumper.utils.util import smkdirs, uopen
from dokuWikiDumper.utils.util import print_with_lock as print


@dataclass
class DumpPageParams:
    dump_dir: str
    get_source: Callable
    title_index: int
    title: str
    doku_url: str
    session: Session
    current_only: bool

exit_event = threading.Event()

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

    task_templ = DumpPageParams(dump_dir=dump_dir, doku_url=doku_url, session=session, get_source=get_source, current_only=current_only,
                          title_index=-999, title="dokuwikidumper_placehold")

    tasks_queue: queue.Queue[DumpPageParams] = queue.Queue(maxsize=threads)

    def task_generator():
        for index, title in enumerate(titles):
            task = copy.copy(task_templ)
            task.title_index = index
            task.title = title
            tasks_queue.put(task)
            print('Content: (%d/%d): [[%s]] ...' % (index+1, len(titles), title))

            if exit_event.is_set():
                print('task generator exit (exit event set)')
                return

        tasks_queue.join()
        print('All tasks done, terminating workers...')
        exit_event.set()

    tg_thread = threading.Thread(target=task_generator, name='task-generator')
    tg_thread.daemon = True
    tg_thread.start()

    with concurrent.futures.ThreadPoolExecutor(max_workers=threads) as executor:
        futures = set()
        while not exit_event.is_set():
            try:
                task = tasks_queue.get(timeout=1)
            except queue.Empty:
                continue
            f = executor.submit(_dump_action, task, ignore_errors, ignore_action_disabled_edit)
            f.add_done_callback(lambda f: tasks_queue.task_done())
            futures.add(f)

            if len(futures) >= threads:
                _done, futures = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
                for f in _done:
                    f.result()

        while futures:
            _done, futures = concurrent.futures.wait(futures, return_when=concurrent.futures.FIRST_COMPLETED)
            for f in _done:
                f.result()


    tg_thread.join()


def _dump_action(task: DumpPageParams, ignore_errors: bool, ignore_action_disabled_edit: bool):
    try:
        dump_page(task)
    except Exception as e:
        if isinstance(e, ActionEditDisabled) and ignore_action_disabled_edit:
            print('[',task.title_index,'] action disabled: edit. ignored')
        elif isinstance(e, ActionEditTextareaNotFound) and ignore_action_disabled_edit:
            print('[',task.title_index,'] action edit: textarea not found. ignored')
        elif not ignore_errors:
            raise e
        else:
            print('[',task.title_index,'] Error in sub thread: (', e, ') ignored')


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
