from datetime import datetime
import html
import os
import re
from ipaddress import ip_address, IPv4Address, IPv6Address
import time
import urllib.parse as urlparse
import logging

from typing import List, Optional, TypedDict

import requests
from bs4 import BeautifulSoup, Tag

from dokuWikiDumper.exceptions import ActionEditDisabled, ActionEditTextareaNotFound, ActionRevisionsDisabled, DispositionHeaderMissingError, HTTPStatusError, RevisionListNotFound, show_edge_case_warning
from dokuWikiDumper.utils.util import check_int, print_with_lock as print, smkdirs, uopen
from dokuWikiDumper.utils.config import runtime_config


logger = logging.getLogger(__name__)

# args must be same as get_source_edit(), even if not used
def get_source_export(url: str, title: str, rev: str = '', *, session: requests.Session):
    """Export the raw source of a page (at a given revision)"""

    r = session.get(url, params={'id': title, 'rev': rev, 'do': 'export_raw'})
    if r.status_code != 200:
        raise HTTPStatusError(r)

    disposition_ok = 'Content-Disposition' in r.headers
    content_type_ok = 'text/plain' in r.headers.get('content-type', '')
    if disposition_ok or content_type_ok:
        return r.text

    raise DispositionHeaderMissingError(r)


# args must be same as get_source_export(), even if not used
def get_source_edit(url: str, title: str, rev: str = '', *, session: requests.Session):
    """Export the raw source of a page by scraping the edit box content. Yuck."""

    r = session.get(url, params={'id': title, 'rev': rev, 'do': 'edit'})
    soup = BeautifulSoup(r.text, runtime_config.html_parser)
    source = None

    textarea = soup.find('textarea', {'name': 'wikitext'})
    if textarea:
        source = ''.join(textarea.text).strip()
    elif 'Action disabled: source' in r.text:
        raise ActionEditDisabled(title)
    else:
        raise ActionEditTextareaNotFound(title)

    return source

class Revision(TypedDict):
    """ (None if not found or failed) """
    id: Optional[str]
    user: Optional[str]
    sum: Optional[str]
    date: Optional[str]
    minor: bool
    """ default: False """
    sizechange: int
    """ default: 0 """

def get_revisions(doku_url, title: str, session: requests.Session, msg_header: str = '')->List[Revision]:
    """ Get the revisions of a page. This is nontrivial because different versions of DokuWiki return completely different revision HTML.

    Returns a dict with the following keys:
    """

    revs: List[Revision] = []
    rev_tmplate: Revision = {
        'id': None, # str(int)
        'user': None, # str
        'sum': None, # str
        'date': None, # str
        'minor': False, # bool
        'sizechange': 0,
    }

    i = 0
    continue_index = -1
    cont = True

    while cont:
        r = session.get(
            doku_url,
            params={
                'id': title,
                'do': 'revisions',
                'first': str(continue_index)})

        soup = BeautifulSoup(r.text, runtime_config.html_parser)

        lis = None

        # check if form#page__revisions exists
        if page__revisions := soup.find('form', {'id': 'page__revisions'}):
            logger.debug('page__revisions: %s', page__revisions)
            if ul := page__revisions.find('ul'):
                assert isinstance(ul, Tag)
                lis = ul.find_all('li')

        # outdate dokuwiki version? try another way.
        if div_page := soup.find('div', {'class': 'page'}):
            logger.debug('div.page: %s', div_page)
            if ul := div_page.find('ul'):
                assert isinstance(ul, Tag)
                lis = ul.find_all('li')

        if lis is None:
            if err_msg := soup.find('div', {'class': 'error'}):
                if 'Action disabled: revisions' in err_msg.text:
                    raise ActionRevisionsDisabled(title)

            raise RevisionListNotFound(title)

        assert lis is not None

        for li in lis:
            li: Tag
            rev = {}

            checkbox = li.find('input', {'type': 'checkbox'})
            rev_hrefs = li.find_all(
                'a', href=lambda href: isinstance(href, str) and (
                    '&rev=' in href or '?rev=' in href))

            # id: optional(str(id)): rev_id, not title name.
            if checkbox:
                rev['id'] = check_int(checkbox.get('value', None))

            if rev_hrefs and rev.get('id', None) is None:
                obj1 = rev_hrefs[0]['href']
                obj2 = urlparse.urlparse(obj1).query
                obj3 = urlparse.parse_qs(obj2)
                if 'rev' in obj3:
                    rev['id'] = check_int(obj3['rev'][0])
                else:
                    rev['id'] = None
                del (obj1, obj2, obj3)

            # use_hidden_rev
            if rev.get('id', None) is None:
                obj1 = li.find('input', {'type': 'hidden'})
                if obj1 is not None and 'value' in obj1:
                    rev['id'] = check_int(obj1['value'])
                del (obj1)

            # minor: bool
            rev['minor'] = li.has_attr('class') and 'minor' in li['class']

            # summary: optional(str)
            sum_span = li.find_all('span', {'class': 'sum'})
            if sum_span:
                sum_span = sum_span[0]
                sum_text = sum_span.text.split(' ')[1:]
                if sum_span.find_all('bdi'):
                    rev['sum'] = html.unescape(
                        sum_span.find('bdi').text).strip()
                else:
                    rev['sum'] = html.unescape(' '.join(sum_text)).strip()
            else:
                print(msg_header, '    ', repr(
                    li.text).replace('\\n', ' ').strip())
                wikilink1 = li.find('a', {'class': 'wikilink1'})
                text_node = wikilink1 and wikilink1.next and wikilink1.next.next or '' # I have no idea what's the propose of this legacy code
                if text_node.strip():
                    rev['sum'] = html.unescape(text_node).strip(u'\u2013 \n')
                    show_edge_case_warning(reason='sum_span not found and text_node found', r_url=r.url, rev_sum=rev['sum'],
                    wikilink1=wikilink1.decode(),
                    next1=wikilink1.next.decode() if wikilink1.next else None,
                    next2=wikilink1.next.next.decode() if (wikilink1.next and wikilink1.next.next) else None)

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

            _rev: Revision = {**rev_tmplate,**rev}  # merge dicts # type: ignore
            revs.append(_rev)

            i += 1

        # next page
        first = soup.find_all('input', {'name': 'first', 'value': True})
        continue_index = first and max(map(lambda x: int(x['value']), first))
        cont = soup.find('input', {'class': 'button', 'accesskey': 'n'})
        # time.sleep(1.5)

    # if revs and use_hidden_rev and not select_revs:
    #     soup2 = BeautifulSoup(session.get(url, params={'id': title}).text)
    #     revs[0]['id'] = soup2.find(
    #         'input', {
    #             'type': 'hidden', 'name': 'rev', 'value': True})['value']

    return revs


DATE_FORMATS = ["%Y-%m-%d %H:%M", # <https://www.dokuwiki.org/dokuwiki?do=revisions>
                "%Y-%m-%d", # <http://neff.family.name/unwiki/doku.php>
                "%Y/%m/%d", # <https://tjgrant.com/wiki/news?do=revisions>
                "%Y/%m/%d %H:%M",
                "%Y-%m-%d %H:%M:%S",
                "%Y/%m/%d %H:%M:%S",
                
                "%d.%m.%Y %H:%M",
                "%d/%m/%Y %H:%M", # <https://eolienne.f4jr.org/?do=revisions>
                "%d.%m.%Y %H:%M:%S",
                "%d/%m/%Y %H:%M:%S", # <https://aezoo.compute.dtu.dk/doku.php>

                "%d/%m/%Y alle %H:%M", # <http://didawiki.cli.di.unipi.it/> # 01/03/2007 alle 14:20 (16 anni fa)

                "Le %d/%m/%Y, %H:%M", # <https://doc.ubuntu-fr.org> # Le 23/09/2020, 17:01

                "%H:%M %d/%m/%Y", # <https://lsw.wiki/>
                "%d. %m. %Y (%H:%M)", # <https://www.hks.re/wiki/>
                ]
""" Why there are so many date formats in the world? :( """

def save_page_changes(dumpDir, title: str, revs: List[Revision], child_path, msg_header: str):
    changes_file = dumpDir + '/meta/' + title.replace(':', '/') + '.changes'
    if os.path.exists(changes_file):
        print(msg_header, '    meta change file exists:', changes_file)
        return

    revidOfPage: set[str] = set()
    rows2write = []
    # Loop through revisions in reverse.
    for rev in revs[::-1]:
        print(msg_header, '    meta change saving:', rev)
        summary = rev['sum'] and rev['sum'].strip() or ''
        rev_id = str(0)

        ip = '127.0.0.1'
        user = ''
        minor = 'minor' in rev and rev['minor']

        if 'id' in rev and rev['id']:
            rev_id = rev['id']
        else:
            # Different date formats in different versions of DokuWiki.
            # If no ID was found, make one up based on the date (since rev IDs are Unix times)
            # Maybe this is evil. Not sure.

            print(msg_header, '    One revision of [[%s]] missing rev_id. Using date to rebuild...'
                    % title, end=' ')
            
            assert rev['date'] is not None, 'unknown rev id and unknown rev date: %s' % rev

            for date_format in DATE_FORMATS:
                try:
                    date = datetime.strptime(
                        # remove " (x days ago)" in f"{date_format} (x days ago)" if date_format not contain '('
                        rev['date'].split('(')[0].strip(),
                        date_format
                    ) if '(' not in date_format else datetime.strptime(
                        # date_format contain '('
                        rev['date'].strip(),
                        date_format
                    )
                    rev_id = str(int(time.mktime(date.utctimetuple())))
                    break
                except Exception:
                    rev_id = None
                    
            assert rev_id is not None, 'Cannot parse date: %s' % rev['date']
            assert isinstance(rev_id, str), 'rev_id must be str, not %s' % type(rev_id)

            # if rev_id is not unique, plus 1 to it until it is.
            while rev_id in revidOfPage:
                rev_id = str(int(rev_id) + 1)
            print(msg_header, 'rev_id is now %s' % rev_id)

        revidOfPage.add(rev_id)

        rev['user'] = rev['user'] if rev['user'] is not None else 'unknown'
        try:
            ip_parsed = ip_address(rev['user'])
            assert isinstance(ip_parsed, (IPv4Address, IPv6Address))
            ip = rev['user']
        except ValueError:
            user = rev['user']

        sizechange = rev['sizechange'] or ''

        extra = ''  # TODO: use this
        # max 255 chars(utf-8) for summary. (dokuwiki limitation)
        summary = summary[:255]
        row = '\t'.join([rev_id, ip, 'e' if minor else 'E',
                        title, user, summary, extra, str(sizechange)])
        row = row.replace('\n', ' ')
        row = row.replace('\r', ' ')
        rows2write.append(row)


    smkdirs(dumpDir, '/meta/' + child_path)
    with uopen(changes_file, 'w') as f:
        f.write('\n'.join(rows2write)+'\n')
