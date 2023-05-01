import builtins
import os
from datetime import datetime
import socket
import time
import threading

from bs4 import BeautifulSoup
from requests import Session

from dokuWikiDumper.exceptions import ActionEditDisabled, ActionEditTextareaNotFound, DispositionHeaderMissingError


from .revisions import getRevisions, getSourceEdit, getSourceExport
from .titles import getTitles
from dokuWikiDumper.utils.util import loadTitles, smkdirs, uopen
from dokuWikiDumper.utils.util import print_with_lock as print


sub_thread_error = None


def dumpContent(doku_url: str = '', dumpDir: str = '', session: Session = None, skipTo: int = 0,
                threads: int = 1, ignore_errors: bool = False, ignore_action_disabled_edit: bool = False,
                ignore_disposition_header_missing: bool=False, current_only: bool = False):
    if not dumpDir:
        raise ValueError('dumpDir must be set')

    titles = loadTitles(titlesFilePath=dumpDir + '/dumpMeta/titles.txt')
    if titles is None:
        titles = getTitles(url=doku_url, session=session)
        with uopen(dumpDir + '/dumpMeta/titles.txt', 'w') as f:
            f.write('\n'.join(titles))
            f.write('\n--END--\n')

    if not len(titles):
        print('Empty wiki')
        return False

    r1 = session.get(doku_url, params={'id': titles[0], 'do': 'export_raw'})
    r2 = session.get(doku_url, params={'id': titles[0]})
    r3 = session.get(doku_url, params={'id': titles[0], 'do': 'diff'})

    getSource = getSourceExport
    if 'html' in r1.headers['content-type']:
        print('\nWarning: export_raw action not available, using edit action\n')
        time.sleep(3)
        getSource = getSourceEdit

    soup = BeautifulSoup(r2.text, os.environ.get('htmlparser'))
    hidden_rev = soup.findAll(
        'input', {
            'type': 'hidden', 'name': 'rev', 'value': True})
    use_hidden_rev = hidden_rev and hidden_rev[0]['value']
    # TODO: what the `use_hidden_rev` is for?

    soup = BeautifulSoup(r3.text, os.environ.get('htmlparser'))
    select_revs = soup.findAll(
        'select', {
            'class': 'quickselect', 'name': 'rev2[0]'})
    # TODO: what the `select_revs` is for?

    index_of_title = -1  # 0-based
    if skipTo > 0:
        index_of_title = skipTo - 2
        titles = titles[skipTo-1:]

    def try_dump_page(*args, **kwargs):
        try:
            dump_page(*args, **kwargs)
        except Exception as e:
            if isinstance(e, ActionEditDisabled) and ignore_action_disabled_edit:
                print('[',args[2]+1,'] action disabled: edit. ignored')
            elif isinstance(e, ActionEditTextareaNotFound) and ignore_action_disabled_edit:
                print('[',args[2]+1,'] action edit: textarea not found. ignored')
            elif not ignore_errors:
                global sub_thread_error
                sub_thread_error = e
                raise e
            else:
                print('[',args[2]+1,']Error in sub thread: (', e, ') ignored')
    for title in titles:
        while threading.active_count() > threads:
            time.sleep(0.1)
        if sub_thread_error:
            raise sub_thread_error

        index_of_title += 1
        t = threading.Thread(target=try_dump_page, args=(dumpDir,
                                                     getSource,
                                                     index_of_title,
                                                     title,
                                                     doku_url,
                                                     session,
                                                     use_hidden_rev,
                                                     select_revs,
                                                     current_only,
                                                     ignore_disposition_header_missing,
                                                     ))
        print('Content: (%d/%d): [[%s]] ...' % (index_of_title+1, len(titles), title))
        t.daemon = True
        t.start()

    while threading.active_count() > 1:
        time.sleep(2)
        print('Waiting for %d threads to finish' %
              (threading.active_count() - 1), end='\r')


def dump_page(dumpDir: str,
              getSource,
              index_of_title: int,
              title: str,
              doku_url: str,
              session: Session,
              use_hidden_rev,
              select_revs,
              current_only: bool,
              ignore_disposition_header_missing: bool):
    srouce = getSource(doku_url, title, session=session,
                       ignore_disposition_header_missing=ignore_disposition_header_missing)
    msg_header = '['+str(index_of_title + 1)+']: '
    child_path = title.replace(':', '/')
    child_path = child_path.lstrip('/')
    child_path = '/'.join(child_path.split('/')[:-1])

    smkdirs(dumpDir, '/pages/' + child_path)
    with uopen(dumpDir + '/pages/' + title.replace(':', '/') + '.txt', 'w') as f:
        f.write(srouce)

    if current_only:
        print(msg_header, '    [[%s]] saved.' % (title))
        return

    revs = getRevisions(doku_url, title, use_hidden_rev,
                        select_revs, session=session, msg_header=msg_header)

    revidOfPage: set[str] = set()
    for rev in revs[1:]:
        if 'id' in rev and rev['id']:
            try:
                txt = getSource(doku_url, title, rev['id'], session=session,
                                ignore_disposition_header_missing=ignore_disposition_header_missing)
                smkdirs(dumpDir, '/attic/' + child_path)
                with uopen(dumpDir + '/attic/' + title.replace(':', '/') + '.' + rev['id'] + '.txt', 'w') as f:
                    f.write(txt)
                print(msg_header, '    Revision %s of [[%s]] saved.' % (
                    rev['id'], title))
            except DispositionHeaderMissingError:
                print(msg_header, '    Revision %s of [[%s]] is empty. (probably deleted)' % (
                    rev['id'], title))

            # time.sleep(1.5)

    smkdirs(dumpDir, '/meta/' + child_path)
    with uopen(dumpDir + '/meta/' + title.replace(':', '/') + '.changes', 'w') as f:
        # Loop through revisions in reverse.
        for rev in revs[::-1]:
            print(msg_header, '    meta change saving:', rev)
            sum = 'sum' in rev and rev['sum'].strip() or ''
            id = str(0)

            ip = '127.0.0.1'
            user = ''
            minor = 'minor' in rev and rev['minor']

            if 'id' in rev and rev['id']:
                id = rev['id']
            else:
                # Different date formats in different versions of DokuWiki.
                # If no ID was found, make one up based on the date (since rev IDs are Unix times)
                # Maybe this is evil. Not sure.

                print(
                    msg_header, '    One revision of [[%s]] missing rev_id. Using date to rebuild...' % title, end=' ')
                date_formats = ["%Y-%m-%d %H:%M", "%Y/%m/%d %H:%M", "%d.%m.%Y %H:%M", "%d/%m/%Y %H:%M"]
                # Try each date format until one works.
                # Example below:
                # %Y-%m-%d %H:%M | <https://www.dokuwiki.org/dokuwiki?do=revisions> # 2019/01/01 00:00
                # TODO: %Y-%m-%d %H:%M
                # TODO: %Y/%m/%d %H:%M
                # %d/%m/%Y %H:%M | <https://eolienne.f4jr.org/?do=revisions> #  28/02/2013 12:12
                for date_format in date_formats:
                    try:
                        date = datetime.strptime(rev['date'], date_format)
                        id = str(int(time.mktime(date.utctimetuple())))
                        break
                    except:
                        id = None
                       

                # if rev_id is not unique, plus 1 to it until it is.
                while id in revidOfPage:
                    id = str(int(id) + 1)
                print(msg_header, 'rev_id is now %s' % id)

            revidOfPage.add(id)

            rev['user'] = rev['user'] if 'user' in rev else 'unknown'
            try:
                # inet_aton throws an exception if its argument is not an IPv4 address
                socket.inet_aton(rev['user'])
                ip = rev['user']
            except socket.error:
                user = rev['user']

            sizechange = rev['sizechange'] if 'sizechange' in rev else ''

            extra = ''  # TODO: use this
            # max 255 chars(utf-8) for summary. (dokuwiki limitation)
            sum = sum[:255]
            row = '\t'.join([id, ip, 'e' if minor else 'E',
                            title, user, sum, extra, str(sizechange)])
            row = row.replace('\n', ' ')
            row = row.replace('\r', ' ')

            f.write((row + '\n'))
