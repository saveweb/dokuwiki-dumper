import urllib.parse as urlparse
from bs4 import BeautifulSoup
import requests
from dokuWikiDumper.exceptions import ActionIndexDisabled
from dokuWikiDumper.utils.util import load_titles, print_with_lock as print, uopen
from dokuWikiDumper.utils.config import runtime_config

def get_titles(url, ns=None, session: requests.Session=None, use_legacy_method=None):
    """Get titles given a doku.php URL and an (optional) namespace

    :param `use_legacy_method`: `bool|None`. `None` will auto-detect if ajax api is enabled"""

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
    if use_legacy_method is None:
    # Don't know if ajax api is enabled
        try:
            print('Trying AJAX API (~15s...)')
            # use requests directly to avoid the session retry
            r = requests.post(ajax, data=params, timeout=15, # a timeout to avoid hanging
                headers=session.headers, proxies=session.proxies,
                verify=session.verify,cookies=session.cookies)
            r.raise_for_status()
            # ajax API OK
            use_legacy_method = False
        except requests.exceptions.RequestException as e:
            use_legacy_method = True
            print(str(e))

        if r and (r.status_code != 200 or "AJAX call 'index' unknown!" in r.text):
            use_legacy_method = True

    assert use_legacy_method is not None
    if use_legacy_method is True:
        print('AJAX API not enabled? Using legacy method...')
        return get_titles_legacy(url, ns=None, session=session)
    
    assert use_legacy_method is False
    r = session.post(ajax, data=params) if r is None else r # reuse the previous Response if possible
    soup = BeautifulSoup(r.text, runtime_config.html_parser)
    for a in soup.find_all('a', href=True):
        if a.has_attr('title'):
            title = a['title']
        elif a.has_attr('data-wiki-id'): 
            # for https://wiki.eternal-twin.net/start?do=index
            # (log: https://cdn.digitaldragon.dev/wikibot/jobs/4efda8bd-3bd2-4f59-81ef-8e37cf574431/log.txt)
            title = a['data-wiki-id']
        else:
            query = urlparse.parse_qs(urlparse.urlparse(a['href']).query)
            title = (query['idx' if 'idx' in query else 'id'])[0]
        if 'idx_dir' in a['class']:
            titles += get_titles(url=url, ns=title, session=session, use_legacy_method=use_legacy_method)
        else:
            titles.append(title)
    # time.sleep(1.5)
    print('%sFound %d title(s) in namespace %s' %
          (' ' * depth, len(titles), ns or '(all)'))
    return titles


def get_titles_legacy(url, ns=None, session:requests.Session=None):
    """Get titles using the doku.php?do=index"""

    titles = []
    params = {'do': 'index'}

    if ns:
        params['idx'] = ns
    ns = ns or ''
    depth = len(ns.split(':'))

    r = session.get(url, params=params)
    soup = BeautifulSoup(r.text, runtime_config.html_parser).find_all('ul', {'class': 'idx'})[0]

    if ns:
        print('%sSearching in namespace %s' % (' ' * depth, ns))

        def match(href):
            if not href:
                return False
            qs = urlparse.urlparse(href).query
            qs = urlparse.parse_qs(qs)
            return 'idx' in qs and qs['idx'][0] in (ns, ':' + ns)
        try:
            result = soup.find_all(
            'a', {
                'class': 'idx_dir', 'href': match})[0].find_all_previous('li')[0].find_all(
            'a', {
                'href': lambda x: x and not match(x)})
        except:
            if 'Command disabled: index' in r.text:
                raise ActionIndexDisabled
            
            raise

    else:
        print('Finding titles (?do=index)')
        result = soup.find_all('a')

    for a in result:
        query = urlparse.parse_qs(urlparse.urlparse(a['href']).query)
        if (
            a.has_attr('class')
            and ('idx_dir' in a['class'])
        ):
            titles += get_titles_legacy(url, query['idx'][0], session=session)
        else:
            titles.append(query['id'][0])

    print('%sFound %d title(s) in namespace %s' %
          (' ' * depth, len(titles), ns or '(all)'))

    return titles


def save_titles(titles: list, dump_dir: str):
    with uopen(dump_dir + '/dumpMeta/titles.txt', 'w') as f:
        f.write('\n'.join(titles))
        f.write('\n--END--\n')

def load_get_save_titles(dump_dir: str, url: str, session: requests.Session):
    """Load titles from dumpMeta/titles.txt, if not exists, get titles from url and save to dumpMeta/titles.txt"""
    titles = load_titles(titles_file_path=dump_dir + '/dumpMeta/titles.txt')
    if titles is None:
        titles = get_titles(url=url, session=session)
        save_titles(titles, dump_dir)
    return titles