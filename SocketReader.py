# A buffered reader of a socket
# Supplies both a line by line reading and also block reading
class SocketReader:
    """ Class to hold request info """
    def __init__(self, sock, read_bytes = 4096):
        self.socket = sock
        self.buffer = ''
        self.buflen = read_bytes

    # This method should read the whole input line by line until connection closes
    # Based on concept from here: http://synack.me/blog/using-python-tcp-sockets
    def readlines(self, delim='\n', recv_buffer=None):
        if recv_buffer == None:
            recv_buffer = self.buflen
        data = True
        while data:
            data = self.socket.recv(recv_buffer)
            self.buffer += data

            while self.buffer.find(delim) != -1:
                line, self.buffer = self.buffer.split(delim, 1)
                yield line
        return

    def get_socket(self):
        return self.socket
    
    def readline(self, delim='\n', recv_buffer=None):
        if recv_buffer == None:
            recv_buffer = self.buflen

        # check if we have a line available in buffer and return it if so
        pos = self.buffer.find(delim)
        if len(self.buffer) > 0 and pos != -1:
            line = self.buffer[:pos + len(delim)]
            self.buffer = self.buffer[pos + len(delim):]
            return line 

        # Else read it from socket
        data = True
        while data:
            data = self.socket.recv(recv_buffer)
            if len(data) == 0:
                raise IOError('Socket closed')

            self.buffer += data

            pos = self.buffer.find(delim)
            if pos != -1:
                line = self.buffer[:pos + len(delim)]
                self.buffer = self.buffer[pos + len(delim):]
                return line 
        return

    def recv(self, recv_buffer=None):
        if recv_buffer == None:
            recv_buffer = self.buflen
        data = ''
#        print 'Trying to read ' + str(recv_buffer) + ' bytes. Current buffer size ' + str(len(self.buffer))
        # check if we have enough data in buffer
        if len(self.buffer) >= recv_buffer:
            data = self.buffer[:recv_buffer]
            self.buffer = self.buffer[recv_buffer:]
#            print "read from buffer"
#            print "returning " + str(len(data)) + " bytes. Current buffer size " + str(len(self.buffer))
            return data

        if len(self.buffer) > 0:
            data = self.buffer
            self.buffer = ''
            return data

        data = self.socket.recv(recv_buffer)
        if len(data) == 0:
            raise IOError('Socket closed')
        return data
