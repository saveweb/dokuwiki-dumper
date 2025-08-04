import os
import threading
import time
import requests
from dokuWikiDumper.dump.content.revisions import get_revisions
from dokuWikiDumper.dump.content.titles import load_get_save_titles
from dokuWikiDumper.utils.util import load_titles, smkdirs, uopen
from dokuWikiDumper.utils.util import print_with_lock as print

from dokuWikiDumper.exceptions import DispositionHeaderMissingError

PDF_DIR = 'pdf/'
PDF_PAGR_DIR = PDF_DIR + 'pages/'
PDF_OLDPAGE_DIR = PDF_DIR + 'attic/'

sub_thread_error = None

def dump_PDF(doku_url, dump_dir,
                  session: requests.Session, threads: int = 1,
                  ignore_errors: bool = False, current_only: bool = False):
    titles = load_get_save_titles(dump_dir=dump_dir, url=doku_url, session=session)
    
    if not len(titles):
        print('Empty wiki')
        return False
    
    def try_to_dump_pdf(*args, **kwargs):
        try:
            _dump_pdf(*args, **kwargs)
        except Exception as e:
            if not ignore_errors:
                global sub_thread_error
                sub_thread_error = e
                raise e
            print('[',args[1]+1,']Error in sub thread: (', e, ') ignored')
    for index, title in enumerate(titles):
        while threading.active_count() > threads:
            time.sleep(0.1)
        if sub_thread_error:
            raise sub_thread_error

        t = threading.Thread(target=try_to_dump_pdf, args=(dump_dir,
                                                    index,
                                                    title,
                                                    doku_url,
                                                    session,
                                                    current_only))
        print('PDF: (%d/%d): [[%s]] ...' % (index+1, len(titles), title))
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
            child_path = title.replace(':', '/')
            child_dir = os.path.dirname(child_path)
            smkdirs(dumpDir, PDF_PAGR_DIR, child_dir)
            with open(file, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(msg_header, '[[%s]]' % title, 'saved')
    
    if current_only:
        return True

    revs = get_revisions(doku_url=doku_url, session=session, title=title, msg_header=msg_header)

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