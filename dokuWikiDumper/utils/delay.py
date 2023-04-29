import threading
import time


class DelaySession:
    """ Monkey patch `requests.Session.send` to add delay """
    def __init__(self, session, msg=None, delay=None, config=None):
        self.session = session
        self.msg = msg
        self.delay = delay
        self.old_send = None

    def hijack(self):
        ''' Don't forget to call `release()` '''
        def new_send(request, **kwargs):
            Delay(msg=self.msg, delay=self.delay)
            return self.old_send(request, **kwargs)
        self.old_send = self.session.send
        self.session.send = new_send

    def release(self):
        ''' Undo monkey patch '''
        self.session.send = self.old_send
        del self


class Delay:
    done: bool = False
    lock: threading.Lock = threading.Lock()

    def animate(self):
        while True:
            with self.lock:
                if self.done:
                    return

                print("\r" + self.ellipses, end="")
                self.ellipses += "."

            time.sleep(0.3)

    def __init__(self, msg=None, delay=None):
        """Add a delay if configured for that"""
        self.ellipses: str = "."

        if delay <= 0:
            return

        if msg:
            self.ellipses = ("Delay %.1fs: %s " % (delay, msg)) + self.ellipses
        else:
            self.ellipses = ("Delay %.1fs " % (delay)) + self.ellipses

        ellipses_animation = threading.Thread(target=self.animate)
        ellipses_animation.daemon = True
        ellipses_animation.start()

        time.sleep(delay)

        with self.lock:
            self.done = True
            print("\r" + " " * len(self.ellipses) + "\r", end="")
