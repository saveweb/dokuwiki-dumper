from datetime import datetime
import socket
import time

from bs4 import BeautifulSoup

from dokuWikiScraper.exceptions import DispositionHeaderMissingError


from .revisions import getRevisions, getSourceEdit, getSourceExport
from .titles import getTitles
from dokuWikiScraper.utils.util import loadTitles, smkdir, uopen


def dumpContent(url:str = '',dumpDir:str = '', session=None, skipTo:int = 0):
    if not dumpDir:
        raise ValueError('dumpDir must be set')
    smkdir(dumpDir + '/pages')
    smkdir(dumpDir + '/attic')
    smkdir(dumpDir + '/meta')
    smkdir(dumpDir + '/dumpMeta')

    titles = loadTitles(titlesFilePath=dumpDir + '/dumpMeta/titles.txt')
    if titles is None:
        titles = getTitles(url=url, session=session)
        with uopen(dumpDir + '/dumpMeta/titles.txt', 'w') as f:
            f.write('\n'.join(titles))
            f.write('\n--END--\n')

    if not len(titles):
        print('Empty wiki')
        return False

    r1 = session.get(url, params={'id': titles[0], 'do': 'export_raw'})
    r2 = session.get(url, params={'id': titles[0]})
    r3 = session.get(url, params={'id': titles[0], 'do': 'diff'})

    getSource = getSourceExport
    if 'html' in r1.headers['content-type']:
        print('Export not available, using edit')
        getSource = getSourceEdit

    soup = BeautifulSoup(r2.text, 'lxml')
    hidden_rev = soup.findAll(
        'input', {
            'type': 'hidden', 'name': 'rev', 'value': True})
    use_hidden_rev = hidden_rev and hidden_rev[0]['value']

    soup = BeautifulSoup(r3.text, 'lxml')
    select_revs = soup.findAll(
        'select', {
            'class': 'quickselect', 'name': 'rev2[0]'})

    indexOfTitle = -1 # # 0-based
    if skipTo > 0:
        indexOfTitle = skipTo - 2
        titles = titles[skipTo-1:]
    for title in titles:
        indexOfTitle += 1
        print('(%d/%d): [[%s]] ...' % (indexOfTitle+1, len(titles), title))
        titleparts = title.split(':')
        for i in range(len(titleparts)):
            dir = "/".join(titleparts[:i])
            smkdir(dumpDir + '/pages/' + dir)
            smkdir(dumpDir + '/meta/' + dir)
            smkdir(dumpDir + '/attic/' + dir)
        with uopen(dumpDir + '/pages/' + title.replace(':', '/') + '.txt', 'w') as f:
            f.write(getSource(url, title, session=session))
        revs = getRevisions(url, title, use_hidden_rev, select_revs, session=session)

        revidOfPage: set[str] = set()
        for rev in revs[1:]:
            if 'id' in rev and rev['id']:
                try:
                    txt = getSource(url, title, rev['id'],session=session)
                    with uopen(dumpDir + '/attic/' + title.replace(':', '/') + '.' + rev['id'] + '.txt', 'w') as f:
                        f.write(txt)
                    print('    Revision %s of [[%s]] saved.' % (rev['id'], title))
                except DispositionHeaderMissingError:
                    print('    Revision %s of [[%s]] is empty. (probably deleted)' % (rev['id'], title))

                # time.sleep(1.5)
        with uopen(dumpDir + '/meta/' + title.replace(':', '/') + '.changes', 'w') as f:
            # Loop through revisions in reverse.
            for rev in revs[::-1]:
                print('    meta change saved:', rev)
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

                    print('    One revision of [[%s]] missing rev_id. Using date to rebuild...' % title, end=' ')
                    try:
                        date = datetime.strptime(rev['date'], "%Y/%m/%d %H:%M")
                        id = str(int(time.mktime(date.utctimetuple())))
                    except:
                        date = datetime.strptime(rev['date'], "%d.%m.%Y %H:%M")
                        id = str(int(time.mktime(date.utctimetuple())))

                    # if rev_id is not unique, plus 1 to it until it is.
                    while id in revidOfPage:
                        id = str(int(id) + 1)
                    print('rev_id is now %s' % id)

                revidOfPage.add(id)


                rev['user'] = rev['user'] if 'user' in rev else 'unknown'
                try:
                    # inet_aton throws an exception if its argument is not an IPv4 address
                    socket.inet_aton(rev['user'])
                    ip = rev['user']
                except socket.error:
                    user = rev['user']


                extra = '' # TODO: use this
                sizechange = '' # TODO: use this
                sum = sum[:255] # max 255 chars(utf-8) for summary. (dokuwiki limitation) 
                row = '\t'.join([id, ip, 'e' if minor else 'E', title, user, sum, extra, sizechange])
                row = row.replace('\n', ' ')
                row = row.replace('\r', ' ')

                f.write((row + '\n'))
