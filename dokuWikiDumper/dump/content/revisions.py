import html
import os
import re
import urllib.parse as urlparse

import requests
from bs4 import BeautifulSoup

from dokuWikiDumper.exceptions import ActionEditDisabled, ActionEditTextareaNotFound, ContentTypeHeaderNotTextPlain, DispositionHeaderMissingError, HTTPStatusError
from dokuWikiDumper.utils.util import check_int, print_with_lock as print


# args must be same as getSourceEdit(), even if not used
def getSourceExport(url, title, rev='', session: requests.Session = None, 
                    ignore_disposition_header_missing: bool=False):
    """Export the raw source of a page (at a given revision)"""

    r = session.get(url, params={'id': title, 'rev': rev, 'do': 'export_raw'})
    if r.status_code != 200:
        raise HTTPStatusError(r)
    if ('Content-Disposition' not in r.headers) and (not ignore_disposition_header_missing):
        raise DispositionHeaderMissingError(r)
    if 'text/plain' not in r.headers.get('content-type'):
        raise ContentTypeHeaderNotTextPlain(r)

    return r.text


# args must be same as getSourceExport(), even if not used
def getSourceEdit(url, title, rev='', session: requests.Session = None,
                  ignore_disposition_header_missing: bool=False):
    """Export the raw source of a page by scraping the edit box content. Yuck."""

    r = session.get(url, params={'id': title, 'rev': rev, 'do': 'edit'})
    soup = BeautifulSoup(r.text, os.environ.get('htmlparser'))
    source = None
    try:
        source = ''.join(soup.find('textarea', {'name': 'wikitext'}).text).strip()
    except AttributeError as e:
        if 'Action disabled: source' in r.text:
            raise ActionEditDisabled(title)
    
    if not source:
        raise ActionEditTextareaNotFound(title)

    return source


def getRevisions(doku_url, title, use_hidden_rev=False, select_revs=False, session: requests.Session = None, msg_header: str = ''):
    """ Get the revisions of a page. This is nontrivial because different versions of DokuWiki return completely different revision HTML.

    Returns a dict with the following keys: (None if not found or failed)
    - id: str|None
    - user: str|None
    - sum: str|None
    - date: str|None
    - minor: bool
    """

    use_hidden_rev = True  # temp fix
    select_revs = False  # temp fix
    revs = []
    rev_tmplate = {
        'id': None, # str(int)
        'user': None, # str
        'sum': None, # str
        'date': None, # str
        'minor': False, # bool
        'sizechange': 0,
    }

    # if select_revs:
    if False:  # disabled, it's not stable.
        r = session.get(doku_url, params={'id': title, 'do': 'diff'})
        soup = BeautifulSoup(r.text, os.environ.get('htmlparser'))
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
            doku_url,
            params={
                'id': title,
                'do': 'revisions',
                'first': continue_index})

        soup = BeautifulSoup(r.text, os.environ.get('htmlparser'))

        try:
            lis = soup.find('form', {'id': 'page__revisions'}).find(
                'ul').findAll('li')
        except AttributeError:
            # outdate dokuwiki version? try another way.
            try:
                lis = soup.find('div', {'class': 'page'}).find(
                    'ul').findAll('li')
            except:
                # still fail
                print(msg_header, 'Error: cannot find revisions list.')
                raise

        for li in lis:
            rev = {}

            checkbox = li.find('input', {'type': 'checkbox'})
            rev_hrefs = li.findAll(
                'a', href=lambda href: href and (
                    '&rev=' in href or '?rev=' in href))

            # id: optional(str(id)): rev_id, not title name.
            if checkbox and rev.get('id', None) is None:
                rev['id'] = checkbox.get('value', None)
                rev['id'] = check_int(rev['id'])

            if rev_hrefs and rev.get('id', None) is None:
                obj1 = rev_hrefs[0]['href']
                obj2 = urlparse.urlparse(obj1).query
                obj3 = urlparse.parse_qs(obj2)
                if 'rev' in obj3:
                    rev['id'] = obj3['rev'][0]
                    rev['id'] = check_int(rev['id'])
                else:
                    rev['id'] = None
                del (obj1, obj2, obj3)

            if use_hidden_rev and rev.get('id', None) is None:
                obj1 = li.find('input', {'type': 'hidden'})
                if obj1 is not None and 'value' in obj1:
                    rev['id'] = obj1['value']
                    rev['id'] = check_int(rev['id'])
                del (obj1)

            # minor: bool
            rev['minor'] = li.has_attr('class') and 'minor' in li['class']

            # summary: optional(str)
            sum_span = li.findAll('span', {'class': 'sum'})
            if sum_span and not select_revs:
                sum_span = sum_span[0]
                sum_text = sum_span.text.split(' ')[1:]
                if sum_span.findAll('bdi'):
                    rev['sum'] = html.unescape(
                        sum_span.find('bdi').text).strip()
                else:
                    rev['sum'] = html.unescape(' '.join(sum_text)).strip()
            elif not select_revs:
                print(msg_header, '    ', repr(
                    li.text).replace('\\n', ' ').strip())
                wikilink1 = li.find('a', {'class': 'wikilink1'})
                text_node = wikilink1 and wikilink1.next and wikilink1.next.next or ''
                if text_node.strip:
                    rev['sum'] = html.unescape(text_node).strip(u'\u2013 \n')

            # date: optional(str)
            date_span = li.find('span', {'class': 'date'})
            if date_span:
                rev['date'] = date_span.text.strip()
            else:
                rev['date'] = ' '.join(li.text.strip().split(' ')[:2])
                matches = re.findall(
                    r'([0-9./]+ [0-9]{1,2}:[0-9]{1,2})',
                    rev['date'])
                if matches:
                    rev['date'] = matches[0]

            # sizechange: optional(int)
            sizechange_span = li.find('span', {'class': 'sizechange'})

            if sizechange_span:
                sizechange_text = sizechange_span.text.replace('\xC2\xA0', ' ').strip()
                units = ['B', 'KB', 'MB', 'GB']
                positive = '−' not in sizechange_text
                size_change = re.sub(r'[^0-9.]', '', sizechange_text)
                try:
                    size_change = float(size_change)
                except ValueError:
                    size_change = 0.0

                for unit in units[1:]:
                    if unit in sizechange_text:
                        size_change *= 1024
                rev['sizechange'] = positive and int(size_change) or int(-size_change)

            # user: optional(str)
            # legacy
            # if not (select_revs and len(revs) > i and revs[i]['user']):
            user_span = li.find('span', {'class': 'user'})
            if user_span and user_span.text is not None:
                rev['user'] = html.unescape(user_span.text).strip()

            # if select_revs and len(revs) > i:
            #     revs[i].update(rev)
            # else:
            #     revs.append(rev)

            _rev = {**rev_tmplate, **rev}  # merge dicts
            revs.append(_rev)

            i += 1

        # next page
        first = soup.findAll('input', {'name': 'first', 'value': True})
        continue_index = first and max(map(lambda x: int(x['value']), first))
        cont = soup.find('input', {'class': 'button', 'accesskey': 'n'})
        # time.sleep(1.5)

    # if revs and use_hidden_rev and not select_revs:
    #     soup2 = BeautifulSoup(session.get(url, params={'id': title}).text)
    #     revs[0]['id'] = soup2.find(
    #         'input', {
    #             'type': 'hidden', 'name': 'rev', 'value': True})['value']

    return revs
