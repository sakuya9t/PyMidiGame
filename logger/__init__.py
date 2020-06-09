import datetime
import threading
from queue import Queue


class logger(threading.Thread):
    """
    This thread is responsible for logging messages
    """
    def __init__(self):
        super(logger, self).__init__()
        self.buffer = Queue()
        self.alive = True

    def run(self):
        while self.alive:
            if self.buffer.empty():
                continue
            else:
                message = self.buffer.get()
                print(message)

    def info(self, message):
        time = str(datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]"))
        message = str(message)
        self.buffer.put("(INFO) {time} {message}".format(time=time, message=message))

    def error(self, message):
        time = str(datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]"))
        message = str(message)
        self.buffer.put("(ERROR) {time} {message}".format(time=time, message=message))

    def warning(self, message):
        time = str(datetime.datetime.now().strftime("[%Y-%m-%d %H:%M:%S]"))
        message = str(message)
        self.buffer.put("(WARNING) {time} {message}".format(time=time, message=message))

    def exit(self):
        self.alive = False
