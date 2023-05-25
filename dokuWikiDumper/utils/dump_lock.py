import fcntl
import os
import sys

LOCK_FILENAME = 'dumping.lock'

class DumpLock:
    def __init__(self, lock_dir):
        self.lock_file = os.path.join(lock_dir, LOCK_FILENAME)
        self.lock_file_fd = None

    def __enter__(self):
        self.lock_file_fd = open(self.lock_file, 'w')
        try:
            fcntl.lockf(self.lock_file_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            print("Acquired lock, continuing.")
        except IOError:
            print("Another instance is already running, quitting.")
            sys.exit(-1)

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.lock_file_fd is None:
            raise IOError("Lock file not opened.")
        fcntl.lockf(self.lock_file_fd, fcntl.LOCK_UN)
        self.lock_file_fd.close()
        os.remove(self.lock_file)
        print("Released lock.")

    # decorator
    def __call__(self, func):
        def wrapper(*args, **kwargs):
            with self:
                return func(*args, **kwargs)
        return wrapper