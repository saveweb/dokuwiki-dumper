from html.parser import HTMLParser
import re
import urllib.parse as urlparse
from bs4 import BeautifulSoup


def getSourceExport(url, title, rev='', session=None):
    """Export the raw source of a page (at a given revision)"""

    r = session.get(url, params={'id': title, 'rev': rev, 'do': 'export_raw'})
    if r.status_code != 200:
        raise Exception('Error exporting: title=%s, rev=%s , HTTP status code: %d' % (title, rev, r.status_code))
    if 'Content-Disposition' not in r.headers:
        raise Exception('Error exporting: title=%s, rev=%s , No Content-Disposition header' % (title, rev))
    
    return r.text


def getSourceEdit(url, title, rev='', session=None):
    """Export the raw source of a page by scraping the edit box content. Yuck."""

    r = session.get(url, params={'id': title, 'rev': rev, 'do': 'edit'})
    soup = BeautifulSoup(r.text, 'lxml')
    return ''.join(soup.find('textarea', {'name': 'wikitext'}).text).strip()


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