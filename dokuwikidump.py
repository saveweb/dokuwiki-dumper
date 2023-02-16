# dumpgenerator.py A generator of dumps for wikis
# Copyright (C) 2011-2014 WikiTeam developers
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

try:
    from bs4 import BeautifulSoup
except:
    print('Need BeautifulSoup for current version. In the future it should use regex for scraping.')

from html.parser import HTMLParser
import urllib.parse as urlparse
import requests
import os
import socket
import re
from datetime import datetime
import gzip
import time

def createSession():
    session = requests.Session()
    try:
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        # Courtesy datashaman https://stackoverflow.com/a/35504626
        class CustomRetry(Retry):
            def increment(self, method=None, url=None, *args, **kwargs):
                if '_pool' in kwargs:
                    conn = kwargs['_pool'] # type: urllib3.connectionpool.HTTPSConnectionPool
                    if 'response' in kwargs:
                        try:
                            # drain conn in advance so that it won't be put back into conn.pool
                            kwargs['response'].drain_conn()
                        except:
                            pass
                    # Useless, retry happens inside urllib3
                    # for adapters in session.adapters.values():
                    #     adapters: HTTPAdapter
                    #     adapters.poolmanager.clear()

                    # Close existing connection so that a new connection will be used
                    if hasattr(conn, 'pool'):
                        pool = conn.pool  # type: queue.Queue
                        try:
                            # Don't directly use this, This closes connection pool by making conn.pool = None
                            conn.close()
                        except:
                            pass
                        conn.pool = pool
                return super(CustomRetry, self).increment(method=method, url=url, *args, **kwargs)

            def sleep(self, response=None):
                backoff = self.get_backoff_time()
                if backoff <= 0:
                    return
                if response is not None:
                    msg = 'req retry (%s)' % response.status
                else:
                    msg = None
                time.sleep(backoff) 

        __retries__ = CustomRetry(
            total=5, backoff_factor=1.5,
            status_forcelist=[500, 502, 503, 504, 429],
            allowed_methods=['DELETE', 'PUT', 'GET', 'OPTIONS', 'TRACE', 'HEAD', 'POST']
        )
        session.mount("https://", HTTPAdapter(max_retries=__retries__))
        session.mount("http://", HTTPAdapter(max_retries=__retries__))
    except:
        pass
    return session

def getTitles(url, ns=None, session=None):
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
    soup = BeautifulSoup(r.text, 'lxml')
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
    print('%sFound %d title(s) in namespace %s' % (' ' * depth, len(titles), ns or '(all)'))
    return titles


def getTitlesOld(url, ns=None, ancient=False, session=None):
    """Get titles using the doku.php?do=index"""

    titles = []
    params = {'do': 'index'}

    if ns:
        params['idx'] = ns
    ns = ns or ''
    depth = len(ns.split(':'))

    r = session.get(url, params=params)
    soup = BeautifulSoup(r.text, 'lxml').findAll('ul', {'class': 'idx'})[0]
    attr = 'text' if ancient else 'title'

    if ns:
        print('%sSearching in namespace %s' % (' ' * depth, ns))

        def match(href):
            if not href:
                return False
            qs = urlparse.urlparse(href).query
            qs = urlparse.parse_qs(qs)
            return 'idx' in qs and qs['idx'][0] in (ns, ':' + ns)
        result = soup.findAll(
            'a', {
                'class': 'idx_dir', 'href': match})[0].findAllPrevious('li')[0].findAll(
            'a', {
                'href': lambda x: x and not match(x)})
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

    print('%sFound %d title(s) in namespace %s' % (' ' * depth, len(titles), ns or '(all)'))

    return titles


def getSourceExport(url, title, rev='', session=None):
    """Export the raw source of a page (at a given revision)"""

    r = session.get(url, params={'id': title, 'rev': rev, 'do': 'export_raw'})
    return r.text


def getSourceEdit(url, title, rev='', session=None):
    """Export the raw source of a page by scraping the edit box content. Yuck."""

    r = session.get(url, params={'id': title, 'rev': rev, 'do': 'edit'})
    soup = BeautifulSoup(r.text, 'lxml')
    return ''.join(soup.find('textarea', {'name': 'wikitext'}).text).strip()


def url2prefix(url):
    """Convert URL to a valid prefix filename."""

    # At this point, both api and index are supposed to be defined

    # use request to transform prefix into a valid filename
    
    r = urlparse.urlparse(url)
    # prefix = r.netloc + r.path
    if r.path and r.path != '/' and not r.path.endswith('/'):
        # truncate to last slash
        prefix = r.netloc + r.path[:r.path.rfind('/')]
    else:
        prefix = r.netloc + r.path
    prefix = prefix.lower()
    prefix = re.sub(r"(/[a-z0-9]+\.php)", "", prefix)
    prefix = prefix.strip('/')
    prefix = re.sub(r"/", "_", prefix)

    # domain = re.sub(r"\.", "", domain)
    # domain = re.sub(r"[^A-Za-z0-9]", "_", domain)

    return prefix


def getRevisions(url, title, use_hidden_rev=False, select_revs=False, session=None):
    """ Get the revisions of a page. This is nontrivial because different versions of DokuWiki return completely different revision HTML."""

    revs = []
    h = HTMLParser
    if select_revs:
        r = session.get(url, params={'id': title, 'do': 'diff'})
        soup = BeautifulSoup(r.text, 'lxml')
        select = soup.find(
            'select', {
                'class': 'quickselect', 'name': 'rev2[1]'})
        for option in select.findAll('option'):
            text = option.text
            date = ' '.join(text.split(' ')[:2])
            username = len(text.split(' ')) > 2 and text.split(' ')[2]
            summary = ' '.join(text.split(' ')[3:])

            revs.append({'id': option['value'],
                         'user': username,
                         'sum': summary,
                         'date': date})

    i = 0
    continue_index = -1
    cont = True

    while cont:
        r = session.get(
            url,
            params={
                'id': title,
                'do': 'revisions',
                'first': continue_index})

        soup = BeautifulSoup(r.text, 'lxml')
        lis = soup.findAll(
            'div', {
                'class': 'level1'})[0].findNext('ul').findAll('li')

        for li in lis:
            rev = {}
            rev_hrefs = li.findAll(
                'a', href=lambda href: href and (
                    '&rev=' in href or '?rev=' in href))
            rev['minor'] = ('class', 'minor') in li.attrs

            if rev_hrefs:
                obj1 = rev_hrefs[0]['href']
                obj2 = urlparse.urlparse(obj1).query
                obj3 = urlparse.parse_qs(obj2)
                if 'rev' in obj3:
                    rev['id'] = obj3['rev'][0]
                else:
                    rev['id'] = None
                del(obj1, obj2, obj3)
                

            sum_span = li.findAll('span', {'class': 'sum'})
            if sum_span and not select_revs:
                sum_span = sum_span[0]
                sum_text = sum_span.text.split(' ')[1:]
                if sum_span.findAll('bdi'):
                    rev['sum'] = h.unescape(sum_span.find('bdi').text).strip()
                else:
                    rev['sum'] = h.unescape(' '.join(sum_text)).strip()
            elif not select_revs:
                print(repr(li.text))
                wikilink1 = li.find('a', {'class': 'wikilink1'})
                text_node = wikilink1 and wikilink1.next and wikilink1.next.next or ''
                if text_node.strip:
                    rev['sum'] = h.unescape(text_node).strip(u'\u2013 \n')

            date_span = li.find('span', {'class': 'date'})
            if date_span:
                rev['date'] = date_span.text.strip()
            else:
                rev['date'] = ' '.join(li.text.split(' ')[:2])
                matches = re.findall(
                    r'([0-9./]+ [0-9]{1,2}:[0-9]{1,2})',
                    rev['date'])
                if matches:
                    rev['date'] = matches[0]

            if not (select_revs and len(revs) > i and revs[i]['user']):
                user_span = li.find('span', {'class': 'user'})
                if user_span:
                    rev['user'] = user_span.text

            if select_revs and len(revs) > i:
                revs[i].update(rev)
            else:
                revs.append(rev)
            i += 1

        first = soup.findAll('input', {'name': 'first', 'value': True})
        continue_index = first and max(map(lambda x: x['value'], first))
        cont = soup.find('input', {'class': 'button', 'accesskey': 'n'})
        # time.sleep(1.5)

    if revs and use_hidden_rev and not select_revs:
        soup2 = BeautifulSoup(session.get(url, params={'id': title}).text)
        revs[0]['id'] = soup2.find(
            'input', {
                'type': 'hidden', 'name': 'rev', 'value': True})['value']

    return revs


def getFiles(url, ns='', session=None):
    """ Return a list of media filenames of a wiki """
    files = set()
    ajax = urlparse.urljoin(url, 'lib/exe/ajax.php')
    medialist = BeautifulSoup(
        session.post(ajax, {
            'call': 'medialist',
            'ns': ns,
            'do': 'media'
        }).text, 'lxml')
    medians = BeautifulSoup(
        session.post(ajax, {
            'call': 'medians',
            'ns': ns,
            'do': 'media'
        }).text, 'lxml')
    imagelinks = medialist.findAll(
        'a',
        href=lambda x: x and re.findall(
            '[?&](media|image)=',
            x))
    for a in imagelinks:
        query = urlparse.parse_qs(urlparse.urlparse(a['href']).query)
        key = 'media' if 'media' in query else 'image'
        files.add(query[key][0])
    files = list(files)
    namespacelinks = medians.findAll('a', {'class': 'idx_dir', 'href': True})
    for a in namespacelinks:
        query = urlparse.parse_qs(urlparse.urlparse(a['href']).query)
        files += getFiles(url, query['ns'][0], session=session)
    print('Found %d files in namespace %s' % (len(files), ns or '(all)'))
    return files


def loadTitles(titlesFilePath) -> list[str]|None:
    """ Load titles from dump directory
    
    Return:
        `list[str]`: titles
        `None`: titles file does not exist or incomplete
     """
    if os.path.exists(titlesFilePath):
        with open(titlesFilePath, 'r') as f:
            titles = f.read().splitlines()
        if len(titles) and titles[-1] == '--END--':
            print('Loaded %d titles from %s' % (len(titles) - 1, titlesFile))
            return titles[:-1]
    
    return None


def dumpContent(url:str = '',dumpDir:str = '', session=None):
    if not dumpDir:
        raise ValueError('dumpDir must be set')
    mkdir(dumpDir + '/pages')
    mkdir(dumpDir + '/attic')
    mkdir(dumpDir + '/meta')
    mkdir(dumpDir + '/dumpMeta')

    titles = loadTitles(titlesFilePath=dumpDir + '/dumpMeta/titles.txt')
    if titles is None:
        titles = getTitles(url=url, session=session)
        with open(dumpDir + '/dumpMeta/titles.txt', 'w') as f:
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

    for title in titles:
        titleparts = title.split(':')
        for i in range(len(titleparts)):
            dir = "/".join(titleparts[:i])
            mkdir(dumpDir + '/pages/' + dir)
            mkdir(dumpDir + '/meta/' + dir)
            mkdir(dumpDir + '/attic/' + dir)
        with open(dumpDir + '/pages/' + title.replace(':', '/') + '.txt', 'w') as f:
            f.write(getSource(url, title, session=session))
        revs = getRevisions(url, title, use_hidden_rev, select_revs, session=session)
        for rev in revs[1:]:
            if 'id' in rev and rev['id']:
                with open(dumpDir + '/attic/' + title.replace(':', '/') + '.' + rev['id'] + '.txt', 'w') as f:
                    f.write(getSource(url, title, rev['id'],session=session))
                # time.sleep(1.5)
                print('Revision %s of %s' % (rev['id'], title))
        with open(dumpDir + '/meta/' + title.replace(':', '/') + '.changes', 'w') as f:
            # Loop through revisions in reverse.
            for rev in revs[::-1]:
                print(rev, title)
                sum = 'sum' in rev and rev['sum'].strip() or ''
                id = 0

                ip = '127.0.0.1'
                user = ''
                minor = 'minor' in rev and rev['minor']

                if 'id' in rev and rev['id']:
                    id = rev['id']
                else:
                    # Different date formats in different versions of DokuWiki.
                    # If no ID was found, make one up based on the date (since rev IDs are Unix times)
                    # Maybe this is evil. Not sure.

                    try:
                        date = datetime.strptime(rev['date'], "%Y/%m/%d %H:%M")
                        id = str(int(time.mktime(date.utctimetuple())))
                    except:
                        date = datetime.strptime(rev['date'], "%d.%m.%Y %H:%M")
                        id = str(int(time.mktime(date.utctimetuple())))

                rev['user'] = rev['user'] if 'user' in rev else 'unknown'
                try:
                    # inet_aton throws an exception if its argument is not an IPv4 address
                    socket.inet_aton(rev['user'])
                    ip = rev['user']
                except socket.error:
                    user = rev['user']

                row = '\t'.join([id, ip, 'e' if minor else 'E', title, user, sum])
                row = row.replace('\n', ' ')
                row = row.replace('\r', ' ')

                f.write((row + '\n'))


def dumpMedia(url: str = '', dumpDir: str = '', session=None):
    if not dumpDir:
        raise ValueError('dumpDir must be set')
    prefix = dumpDir
    mkdir(prefix + '/media')
    mkdir(prefix + '/media_attic')
    mkdir(prefix + '/media_meta')

    fetch = urlparse.urljoin(url, 'lib/exe/fetch.php')

    files = getFiles(url, session=session)
    for title in files:
        titleparts = title.split(':')
        for i in range(len(titleparts)):
            dir = "/".join(titleparts[:i])
            mkdir(prefix + '/media/' + dir)
        with open(prefix + '/media/' + title.replace(':', '/'), 'wb') as f:
            f.write(session.get(fetch, params={'media': title}).content)
        print('File %s' % title)
        # time.sleep(1.5)


def standardizeUrl(url: str = ''):
    if not url.startswith('http'):
        url = 'http://' + url
    return url

def getDokuUrl(url: str = '', session=requests.Session()):
    r = session.get(url)
    dokuUrl = r.url
    
    return dokuUrl

def buildBaseUrl(url: str = '') -> str:
    r = urlparse.urlparse(url)
    path = r.path
    if path and path != '/' and not path.endswith('/'):
        path = path[:path.rfind('/')]
    baseUrl = r.scheme + '://' + r.netloc + path
    if not baseUrl.endswith('/'):
        baseUrl += '/'

    return baseUrl

def mkdir(dir: str = '') -> bool:
    """ Return: True->created, False->existed """
    if not os.path.exists(dir):
        os.mkdir(dir)
        return True

    return False


def dump(urlInput: str = ''):
    session = createSession()
    url = standardizeUrl(urlInput)
    dokuUrl = getDokuUrl(url, session=session)
    baseUrl = buildBaseUrl(dokuUrl)
    dumpDir = url2prefix(dokuUrl)
    print('Dumping to ', dumpDir, '\nBase URL: ', baseUrl, '\nDokuPHP URL: ', dokuUrl)
    mkdir(dumpDir)
    dumpContent(url=dokuUrl, dumpDir=dumpDir, session=session)
    dumpMedia(url=baseUrl, dumpDir=dumpDir, session=session)

dump(input('URL: '))
