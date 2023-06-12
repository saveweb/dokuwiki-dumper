import os
import urllib.parse as urlparse
from bs4 import BeautifulSoup
import requests
from dokuWikiDumper.exceptions import ActionIndexDisabled
from dokuWikiDumper.utils.util import print_with_lock as print
from dokuWikiDumper.utils.config import running_config

def getTitles(url, ns=None, session: requests.Session=None, useOldMethod=None):
    """Get titles given a doku.php URL and an (optional) namespace

    :param `useOldMethod`: `bool|None`. `None` will auto-detect if ajax api is enabled"""


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
    

    r = None
    if useOldMethod is None:
    # Don't know if ajax api is enabled
        try:
            print('Trying AJAX API (~15s...)')
            # use requests directly to avoid the session retry
            r = requests.post(ajax, data=params, timeout=15, # a timeout to avoid hanging
                headers=session.headers, proxies=session.proxies,
                verify=session.verify,cookies=session.cookies)
            r.raise_for_status()
            # ajax API OK
            useOldMethod = False
        except requests.exceptions.RequestException as e:
            useOldMethod = True
            print(str(e))

        if r and (r.status_code != 200 or "AJAX call 'index' unknown!" in r.text):
            useOldMethod = True

    assert useOldMethod is not None
    if useOldMethod is True:
        print('AJAX API not enabled? Using old method...')
        return getTitlesOld(url, ns=None, session=session)
    
    assert useOldMethod is False
    r = session.post(ajax, data=params) if r is None else r # reuse the previous Response if possible
    soup = BeautifulSoup(r.text, running_config.html_parser)
    for a in soup.findAll('a', href=True):
        if a.has_attr('title'):
            title = a['title']
        else:
            query = urlparse.parse_qs(urlparse.urlparse(a['href']).query)
            title = (query['idx' if 'idx' in query else 'id'])[0]
        if 'idx_dir' in a['class']:
            titles += getTitles(url=url, ns=title, session=session, useOldMethod=useOldMethod)
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
    soup = BeautifulSoup(r.text, running_config.html_parser).findAll('ul', {'class': 'idx'})[0]
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
