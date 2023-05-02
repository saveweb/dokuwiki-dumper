import requests
from dokuWikiDumper.utils.delay import Delay
from dokuWikiDumper.utils.util import trim_PHP_warnings


class SessionMonkeyPatch:
    """ Monkey patch `requests.Session.send` to add delay and hard retries
        Monkey patch `requests.Response.text` to trim PHP warnings and handle incorrect encoding
    """
    def __init__(self, session: requests.Session, 
                 msg=None, delay: float=0.0, hard_retries=3,
                 trim_PHP_warnings: bool = False, remove_PHP_warnings_strict_mode: bool = False):

        self.session = session
        self.msg = msg
        self.delay = delay
        self.old_send_method = None
        self.old_text_method = None
        self.hard_retries = hard_retries
        self.trim_PHP_warnings = trim_PHP_warnings
        self.trim_PHP_warnings_strict_mode = remove_PHP_warnings_strict_mode

    def hijack(self):
        ''' Don't forget to call `release()` '''

        # Monkey patch `requests.Session.send`
        self.old_send_method = self.session.send

        def new_send(request, **kwargs):
            hard_retries = self.hard_retries + 1
            if hard_retries <= 0:
                raise ValueError('hard_retries must be positive')

            while hard_retries > 0:
                try:
                    Delay(msg=self.msg, delay=self.delay)
                    return self.old_send_method(request, **kwargs)
                except KeyboardInterrupt:
                    raise
                except Exception as e:
                    hard_retries -= 1
                    if hard_retries <= 0:
                        raise e
                    print('Hard retry... (%d), due to: %s' % (hard_retries, e))

        self.session.send = new_send

        # Monkey patch `requests.Response.text`
        self.old_text_method = requests.Response.text
        def new_text(_self):
            # Handle incorrect encoding
            if _self.encoding is None or _self.encoding == 'ISO-8859-1':
                _self.encoding = _self.apparent_encoding
                if _self.encoding is None:
                    _self.encoding = 'utf-8'

            text = self.old_text_method.fget(_self)
            if self.trim_PHP_warnings:
                text = trim_PHP_warnings(text, strict=self.trim_PHP_warnings_strict_mode)
            return text

        requests.Response.text = property(new_text)

    def release(self):
        ''' Undo monkey patch '''
        self.session.send = self.old_send_method
        requests.Response.text = self.old_text_method
