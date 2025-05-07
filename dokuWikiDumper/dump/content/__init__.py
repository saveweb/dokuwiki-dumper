import copy
from dataclasses import dataclass
import queue
import time
import threading
from typing import Callable, Literal, Union

from requests import Session

from dokuWikiDumper.exceptions import ActionEditDisabled, ActionEditTextareaNotFound, DispositionHeaderMissingError

from .revisions import get_revisions, get_source_edit, get_source_export, save_page_changes
from .titles import get_titles
from dokuWikiDumper.utils.util import load_titles, smkdirs, uopen
from dokuWikiDumper.utils.util import print_with_lock as print

sub_thread_error = None


@dataclass
class DumpPageParams:
    dumpDir: str
    getSource: Callable
    title_index: int
    title: str
    doku_url: str
    session: Session
    current_only: bool


POSION = True


def dump_content(*, doku_url: str, dumpDir: str, session: Session, skipTo: int = 0,
                threads: int = 1, ignore_errors: bool = False, ignore_action_disabled_edit: bool = False, current_only: bool = False):
    if not dumpDir:
        raise ValueError('dumpDir must be set')

    titles = load_titles(titlesFilePath=dumpDir + '/dumpMeta/titles.txt')
    if titles is None:
        titles = get_titles(url=doku_url, session=session)
        with uopen(dumpDir + '/dumpMeta/titles.txt', 'w') as f:
            f.write('\n'.join(titles))
            f.write('\n--END--\n')

    if not len(titles):
        print('Empty wiki')
        return False

    r1 = session.get(doku_url, params={'id': titles[0], 'do': 'export_raw'})

    getSource = get_source_export
    if 'html' in r1.headers['content-type']:
        print('\nWarning: export_raw action not available, using edit action\n')
        time.sleep(3)
        getSource = get_source_edit

    title_index = -1  # 0-based
    if skipTo > 0:
        title_index = skipTo - 2
        titles = titles[skipTo-1:]

    tasks_queue: queue.Queue[Union[DumpPageParams,Literal[True]]] = queue.Queue(maxsize=threads)

    workers: list[threading.Thread] = []
    # spawn workers
    for _ in range(threads):
        t = threading.Thread(target=dump_worker, args=(tasks_queue, ignore_errors, ignore_action_disabled_edit))
        t.daemon = True
        t.start()
        workers.append(t)

    task_templ = DumpPageParams(dumpDir=dumpDir, doku_url=doku_url, session=session, getSource=getSource, current_only=current_only,
                          title_index=-999, title="dokuwikidumper_placehold")

    for title in titles:
        if sub_thread_error:
            raise sub_thread_error

        title_index += 1
        task = copy.copy(task_templ)
        task.title_index = title_index
        task.title = title
        tasks_queue.put(task)
        print('Content: (%d/%d): [[%s]] ...' % (title_index+1, len(titles), title))

    for _ in range(threads):
        tasks_queue.put(POSION)

    tasks_queue.join()

    for w in workers:
        w.join()

    if sub_thread_error:
        raise sub_thread_error


def dump_worker(tasks_queue: queue.Queue[Union[DumpPageParams,Literal[True]]], ignore_errors: bool, ignore_action_disabled_edit: bool):
    global sub_thread_error
    while True:
        task_or_posion = tasks_queue.get()
        if task_or_posion is POSION:
            tasks_queue.task_done()
            break
        task = task_or_posion

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


def dump_page(task: DumpPageParams):
    srouce = task.getSource(task.doku_url, task.title, session=task.session)
    msg_header = '['+str(task.title_index + 1)+']: '
    child_path = task.title.replace(':', '/')
    child_path = child_path.lstrip('/')
    child_path = '/'.join(child_path.split('/')[:-1])

    smkdirs(task.dumpDir, '/pages/' + child_path)
    with uopen(task.dumpDir + '/pages/' + task.title.replace(':', '/') + '.txt', 'w') as f:
        f.write(srouce)

    if task.current_only:
        print(msg_header, '    [[%s]] saved.' % (task.title))
        return

    revs = get_revisions(task.doku_url, task.title, session=task.session, msg_header=msg_header)


    save_page_changes(dumpDir=task.dumpDir, child_path=child_path, title=task.title, 
                       revs=revs, msg_header=msg_header)

    for rev in revs[1:]:
        if 'id' in rev and rev['id']:
            try:
                txt = task.getSource(task.doku_url, task.title, rev['id'], session=task.session)
                smkdirs(task.dumpDir, '/attic/' + child_path)
                with uopen(task.dumpDir + '/attic/' + task.title.replace(':', '/') + '.' + rev['id'] + '.txt', 'w') as f:
                    f.write(txt)
                print(msg_header, '    Revision %s of [[%s]] saved.' % (
                    rev['id'], task.title))
            except DispositionHeaderMissingError:
                print(msg_header, '    Revision %s of [[%s]] is empty. (probably deleted)' % (
                    rev['id'], task.title))
        else:
            print(msg_header, '    Revision %s of [[%s]] failed: %s' % (rev['id'], task.title, 'Rev id not found (please check ?do=revisions of this page)'))
