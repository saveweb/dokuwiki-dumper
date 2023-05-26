import threading
import asyncio


delaying_theads = 0
delaying_theads_lock = threading.Lock()

class Delay:
    done: bool = False
    lock: threading.Lock = threading.Lock()
    delay: float

    async def animate(self):
        while True:
            with self.lock:
                if self.done:
                    return

                with delaying_theads_lock:
                    print("\r" + self.ellipses, end="") if delaying_theads == 1 else None
                self.ellipses += "."

            await asyncio.sleep(0.35)


    def __init__(self, msg=None, delay: float=0.0):
        """Add a delay if configured for that"""
        if delay <= 0:
            return
        self.ellipses: str = "."
        self.delay = delay


        with delaying_theads_lock:
            global delaying_theads
            delaying_theads += 1
            
        if msg:
            self.ellipses = ("Delay %.1fs: %s " % (delay, msg)) + self.ellipses
        else:
            self.ellipses = ("Delay %.1fs " % (delay)) + self.ellipses

        asyncio.run(self.async_tasks())

    async def async_tasks(self):
        task1 = asyncio.create_task(self.animate())
        task2 = asyncio.create_task(self.task_done())
        await task2
        task1.cancel()

    async def task_done(self):
        await asyncio.sleep(self.delay)

        with self.lock and delaying_theads_lock:
            self.done = True
            global delaying_theads
            delaying_theads -= 1
            if delaying_theads == 0: # If this is the last thread, clear the line
                print("\r" + " " * len(self.ellipses) + "\r", end="")
