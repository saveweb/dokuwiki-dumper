import os
import urllib.parse as urlparse
from bs4 import BeautifulSoup
import requests
from dokuWikiDumper.exceptions import ActionIndexDisabled
from dokuWikiDumper.utils.util import print_with_lock as print


def getTitles(url, ns=None, session: requests.Session=None):
    """Get titles given a doku.php URL and an (optional) namespace"""

    # # force use of old method for now
    # return getTitlesOld(url, ns=None, session=session)

    titles = []
    ajax = urlparse.urljoin(url, 'lib/exe/ajax.php')
    params = {'call': 'index'}
    if ns:
        params['idx'] = ns
    else:
        print('Finding titles')
    ns = ns or ''
    depth = len(ns.split(':'))
    if ns:
        print('%sLooking in namespace %s' % (' ' * depth, ns))
    r = session.post(ajax, params)
    if r.status_code != 200 or "AJAX call 'index' unknown!" in r.text:
        return getTitlesOld(url, ns=None, session=session)
    soup = BeautifulSoup(r.text, os.environ.get('htmlparser'))
    for a in soup.findAll('a', href=True):
        if a.has_attr('title'):
            title = a['title']
        else:
            query = urlparse.parse_qs(urlparse.urlparse(a['href']).query)
            title = (query['idx' if 'idx' in query else 'id'])[0]
        if 'idx_dir' in a['class']:
            titles += getTitles(url=url, ns=title, session=session)
        else:
            titles.append(title)
    # time.sleep(1.5)
    print('%sFound %d title(s) in namespace %s' %
          (' ' * depth, len(titles), ns or '(all)'))
    return titles


def getTitlesOld(url, ns=None, ancient=False, session:requests.Session=None):
    """Get titles using the doku.php?do=index"""

    titles = []
    params = {'do': 'index'}

    if ns:
        params['idx'] = ns
    ns = ns or ''
    depth = len(ns.split(':'))

    r = session.get(url, params=params)
    soup = BeautifulSoup(r.text, os.environ.get('htmlparser')).findAll('ul', {'class': 'idx'})[0]
    attr = 'text' if ancient else 'title'

    if ns:
        print('%sSearching in namespace %s' % (' ' * depth, ns))

        def match(href):
            if not href:
                return False
            qs = urlparse.urlparse(href).query
            qs = urlparse.parse_qs(qs)
            return 'idx' in qs and qs['idx'][0] in (ns, ':' + ns)
        try:
            result = soup.findAll(
            'a', {
                'class': 'idx_dir', 'href': match})[0].findAllPrevious('li')[0].findAll(
            'a', {
                'href': lambda x: x and not match(x)})
        except:
            if 'Command disabled: index' in r.text:
                raise ActionIndexDisabled
            
            raise

    else:
        print('Finding titles (?do=index)')
        result = soup.findAll('a')

    for a in result:
        query = urlparse.parse_qs(urlparse.urlparse(a['href']).query)
        if (
            a.has_attr('class')
            and ('idx_dir' in a['class'])
        ):
            titles += getTitlesOld(url, query['idx'][0], session=session)
        else:
            titles.append(query['id'][0])

    print('%sFound %d title(s) in namespace %s' %
          (' ' * depth, len(titles), ns or '(all)'))

    return titles
