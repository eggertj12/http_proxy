# define some special exceptions that we will throw in places
class TimeoutException(Exception):
    pass

class SocketClosedException(Exception):
    pass

