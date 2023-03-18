import queue
import time

import requests
import urllib3

from dokuWikiDumper.__version__ import DUMPER_VERSION


def createSession():
    session = requests.Session()
    try:
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        # Courtesy datashaman https://stackoverflow.com/a/35504626
        class CustomRetry(Retry):
            def increment(self, method=None, url=None, *args, **kwargs):
                if '_pool' in kwargs:
                    # type: urllib3.connectionpool.HTTPSConnectionPool
                    conn = kwargs['_pool']
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
            allowed_methods=['DELETE', 'PUT', 'GET',
                             'OPTIONS', 'TRACE', 'HEAD', 'POST']
        )
        session.mount("https://", HTTPAdapter(max_retries=__retries__))
        session.mount("http://", HTTPAdapter(max_retries=__retries__))
    except:
        pass

    session.headers.update({'User-Agent': 'dokuWikiDumper/' +
                           DUMPER_VERSION + ' (https://github.com/saveweb/dokuwiki-dumper)'})

    return session
