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
        if len(self.buffer) > 0 and self.buffer.find(delim) != -1:
            line, self.buffer = self.buffer.split('\n', 1)
            return line.strip(" \r\n\t")

        data = True
        while data:
            data = self.socket.recv(recv_buffer)
            if len(data) == 0:
                # TODO: handle closed socket
                pass

            self.buffer += data

            if self.buffer.find(delim) != -1:
                line, self.buffer = self.buffer.split('\n', 1)
                return line.strip(" \r\n\t")
        return

    def recv(self, recv_buffer=None):
        if recv_buffer == None:
            recv_buffer = self.buflen
        data = ''
        print 'Trying to read ' + str(recv_buffer) + ' bytes. Current buffer size ' + str(len(self.buffer))
        # check if we have enough data in buffer
        if len(self.buffer) > recv_buffer:
            data = self.buffer[:recv_buffer]
            self.buffer = self.buffer[recv_buffer:]
            print "read from buffer"
            print "returning " + str(len(data)) + " bytes. Current buffer size " + str(len(self.buffer))
            return data

        data = self.socket.recv(recv_buffer)
        print "read " + str(len(data)) + "bytes"
        if len(data) == 0:
            # TODO: handle closed socket
            data = self.buffer
            self.buffer = '';
            print "Nothing recv-ed"
            print "returning " + str(len(data)) + " bytes. Current buffer size " + str(len(self.buffer))
            return data

        self.buffer += data

        if len(self.buffer) > recv_buffer:
            print "read more than enough, bytes read: " + str(len(data))
            data = self.buffer[:recv_buffer]
            self.buffer = self.buffer[:recv_buffer]
        else:
            data = self.buffer
            self.buffer = ''
            print "Read <= requested"

        print "returning " + str(len(data)) + " bytes. Current buffer size " + str(len(self.buffer))
        return data
