import os
import threading
import time
import requests
from dokuWikiDumper.dump.content.revisions import getRevisions
from dokuWikiDumper.dump.content.titles import getTitles

from dokuWikiDumper.utils.util import loadTitles, smkdirs, uopen
from dokuWikiDumper.utils.util import print_with_lock as print

HTML_DIR = 'html/'
HTML_PAGR_DIR = HTML_DIR + 'pages/'
HTML_OLDPAGE_DIR = HTML_DIR + 'attic/'

sub_thread_error = None

def dump_HTML(doku_url, dumpDir,
                  session: requests.Session, skipTo: int = 0, threads: int = 1,
                  ignore_errors: bool = False, current_only: bool = False):
    smkdirs(dumpDir, HTML_PAGR_DIR)

    titles = loadTitles(titlesFilePath=dumpDir + '/dumpMeta/titles.txt')
    if titles is None:
        titles = getTitles(url=doku_url, session=session)
        with uopen(dumpDir + '/dumpMeta/titles.txt', 'w') as f:
            f.write('\n'.join(titles))
            f.write('\n--END--\n')
    
    if not len(titles):
        print('Empty wiki')
        return False
    
    index_of_title = -1  # 0-based
    if skipTo > 0:
        index_of_title = skipTo - 2
        titles = titles[skipTo-1:]

    def try_dump_html_page(*args, **kwargs):
        try:
            dump_html_page(*args, **kwargs)
        except Exception as e:
            if not ignore_errors:
                global sub_thread_error
                sub_thread_error = e
                raise e
            print('[',args[1]+1,']Error in sub thread: (', e, ') ignored')
    for title in titles:
        while threading.active_count() > threads:
            time.sleep(0.1)
        if sub_thread_error:
            raise sub_thread_error

        index_of_title += 1
        t = threading.Thread(target=try_dump_html_page, args=(dumpDir,
                                                    index_of_title,
                                                    title,
                                                    doku_url,
                                                    session,
                                                    current_only))
        print('HTML: (%d/%d): [[%s]] ...' % (index_of_title+1, len(titles), title))
        t.daemon = True
        t.start()

    while threading.active_count() > 1:
        time.sleep(2)
        print('Waiting for %d threads to finish' %
            (threading.active_count() - 1), end='\r')

def dump_html_page(dumpDir, index_of_title, title, doku_url, session: requests.Session, current_only: bool = False):
    r = session.get(doku_url, params={'do': 'export_xhtml', 'id': title})
    # export_html is a alias of export_xhtml
    r.raise_for_status()
    if r.text is None or r.text == '':
        raise Exception(f'Empty response (r.text)')

    msg_header = '['+str(index_of_title + 1)+']: '

    child_path = title.replace(':', '/')
    child_dir = os.path.dirname(child_path)
    html_path = dumpDir + '/' + HTML_PAGR_DIR + child_path + '.html'
    smkdirs(dumpDir, HTML_PAGR_DIR, child_dir)
    with uopen(html_path, 'w') as f:
        f.write(r.text)
        print(msg_header, '[[%s]]' % title, 'saved')
    
    if current_only:
        return True

    revs = getRevisions(doku_url=doku_url, session=session, title=title, msg_header=msg_header)

    for rev in revs[1:]:
        if 'id' in rev and rev['id']:
            try:
                r = session.get(doku_url, params={'do': 'export_xhtml', 'id': title, 'rev': rev['id']})
                r.raise_for_status()
                if r.text is None or r.text == '':
                    raise Exception(f'Empty response (r.text)')
                smkdirs(dumpDir, HTML_OLDPAGE_DIR, child_dir)   
                old_html_path = dumpDir + '/' + HTML_OLDPAGE_DIR + child_path + '.' + rev['id'] + '.html'

                with uopen(old_html_path, 'w') as f:
                    f.write(r.text)
                print(msg_header, '    Revision %s of [[%s]] saved.' % (rev['id'], title))
            except requests.HTTPError as e:
                print(msg_header, '    Revision %s of [[%s]] failed: %s' % (rev['id'], title, e))