import datetime
import logging
from typing import List, Optional

from internetarchive import ArchiveSession, Search

IA_MAX_RETRY = 5
logger = logging.getLogger(__name__)


def ia_s3_tasks_load_avg(session: ArchiveSession) -> float:
    api = "https://s3.us.archive.org/?check_limit=1"
    r = session.get(api, timeout=16)
    r.raise_for_status()
    r_json = r.json()
    total_tasks_queued = r_json["detail"]["total_tasks_queued"]
    total_global_limit = r_json["detail"]["total_global_limit"]
    logger.info(f"ia_s3_load_avg(): {total_tasks_queued} / {total_global_limit}")
    return total_tasks_queued / total_global_limit


def search_ia(ori_url: str, addeddate_intervals: Optional[List[str]] = None):

    ia_session = ArchiveSession()

    subject = 'dokuWikiDumper'
    ori_url2 = ori_url.replace("/doku.php", "")
    ori_url3 = ori_url.replace("/doku.php", "/")

    query = f'(subject:"{subject}" AND (originalurl:"{ori_url}" OR originalurl:"{ori_url2}" OR originalurl:"{ori_url3}"))'
    if addeddate_intervals:
        query += f' AND addeddate:[{addeddate_intervals[0]} TO {addeddate_intervals[1]}]'
    search = Search(ia_session, query=query,
                    fields=['identifier', 'addeddate', 'title', 'subject', 'originalurl', 'uploader', 'item_size'],
                    sorts=['addeddate desc'], # newest first
                    max_retries=IA_MAX_RETRY, # default 5
                    )
    item = None
    for result in search: # only get the first result
        # {'identifier': 'wiki-wikiothingxyz-20230315',
        # 'addeddate': '2023-03-15T01:42:12Z',
        # 'subject': ['wiki', 'wikiteam', 'MediaWiki', .....]}
        if result['originalurl'].lower() in [
            ori_url.lower(),
            ori_url2.lower(),
            ori_url3.lower(),
            ]:
            logger.info(f'Original URL match: {result}')
            yield result
            item = result
        else:
            logger.warning(f'Original URL mismatch: {result}')

    if item is None:
        logger.warning('No suitable dump found at Internet Archive')
        return # skip


def search_ia_recent(ori_url: str, days: int = 365):

    now_utc = datetime.datetime.utcnow()
    now_utc_iso = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")

    one_year_ago = now_utc - datetime.timedelta(days=days)
    one_year_ago_iso = one_year_ago.strftime("%Y-%m-%dT%H:%M:%SZ")

    addeddate_intervals = [one_year_ago_iso, now_utc_iso]

    for item in search_ia(ori_url=ori_url, addeddate_intervals=addeddate_intervals):
        yield item


def any_recent_ia_item_exists(ori_url: str, days: int = 365):
    for item in search_ia_recent(ori_url=ori_url, days=days):
        print('Found an existing dump at Internet Archive')
        print(item)
        print(f'https://archive.org/details/{item["identifier"]}')
        return True

    return False


def search_ia_all(ori_url: str):
    for item in search_ia(ori_url):
        yield item
