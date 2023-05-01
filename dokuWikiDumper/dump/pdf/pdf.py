import os
import threading
import time
import requests
from dokuWikiDumper.dump.content.revisions import getRevisions
from dokuWikiDumper.dump.content.titles import getTitles
from dokuWikiDumper.utils.util import loadTitles, smkdirs, uopen
from dokuWikiDumper.utils.util import print_with_lock as print

from dokuWikiDumper.exceptions import DispositionHeaderMissingError

PDF_DIR = 'pdf/'
PDF_PAGR_DIR = PDF_DIR + 'pages/'
PDF_OLDPAGE_DIR = PDF_DIR + 'attic/'

sub_thread_error = None

def dump_PDF(doku_url, dumpDir,
                  session: requests.Session, skipTo: int = 0, threads: int = 1,
                  ignore_errors: bool = False, current_only: bool = False):

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

    def try_to_dump_pdf(*args, **kwargs):
        try:
            _dump_pdf(*args, **kwargs)
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
        t = threading.Thread(target=try_to_dump_pdf, args=(dumpDir,
                                                    index_of_title,
                                                    title,
                                                    doku_url,
                                                    session,
                                                    current_only))
        print('PDF: (%d/%d): [[%s]] ...' % (index_of_title+1, len(titles), title))
        t.daemon = True
        t.start()

    while threading.active_count() > 1:
        time.sleep(2)
        print('Waiting for %d threads to finish' %
            (threading.active_count() - 1), end='\r')

def _dump_pdf(dumpDir, index_of_title: int, title: str, doku_url, session: requests.Session, current_only: bool = False):
    msg_header = '['+str(index_of_title + 1)+']: '
    file = dumpDir + '/' + PDF_PAGR_DIR + title.replace(':', '/') + '.pdf'
    local_size = -1
    if os.path.isfile(file):
        local_size = os.path.getsize(file)
    with session.get(doku_url, params={'do': 'export_pdf', 'id': title}, stream=True) as r:
        r.raise_for_status()
        if 'Content-Disposition' not in r.headers:
            raise DispositionHeaderMissingError(r)
        remote_size = r.headers.get('Content-Length', -2)

        if local_size == remote_size:
            print(msg_header, '[[%s]]' % title, 'already exists')
        else:
            r.raw.decode_content = True
            child_path = title.replace(':', '/')
            child_dir = os.path.dirname(child_path)
            smkdirs(dumpDir, PDF_PAGR_DIR, child_dir)
            with open(file, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(msg_header, '[[%s]]' % title, 'saved')
    
    if current_only:
        return True

    revs = getRevisions(doku_url=doku_url, session=session, title=title, msg_header=msg_header)

    for rev in revs[1:]:
        if 'id' in rev and rev['id']:
            try:
                r = session.get(doku_url, params={'do': 'export_pdf', 'id': title, 'rev': rev['id']})
                r.raise_for_status()
                content = r.content
                smkdirs(dumpDir, PDF_OLDPAGE_DIR, child_dir)   
                old_pdf_path = dumpDir + '/' + PDF_OLDPAGE_DIR + child_path + '.' + rev['id'] + '.pdf'

                with open(old_pdf_path, 'bw') as f:
                    f.write(content)
                print(msg_header, '    Revision %s of [[%s]] saved.' % (rev['id'], title))
            except requests.HTTPError as e:
                print(msg_header, '    Revision %s of [[%s]] failed: %s' % (rev['id'], title, e))