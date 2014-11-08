import select

from Exceptions import *

# A buffered reader of a socket
# Supplies both a line by line reading and also block reading
class SocketReader:
    READ_SIZE=4096
    TIMEOUT=30

    """ Class to hold request info """
    def __init__(self, sock, read_bytes = READ_SIZE):
        self.socket = sock
        self.buffer = ''
        self.read_size = read_bytes

    # Clean up
    def close(self):
        self.socket.close()
        self.buffer = ''

    # Receives bytes from the socket via the recv function.
    # This function raises an exception on timeout.
    def recv(self, n):
        ready = select.select([self.socket], [], [], self.TIMEOUT)[0]
        if not ready:
            # Raise exception on timeout.
            raise TimeoutException('reading takes too long')

        data = self.socket.recv(n)
        if len(data) == 0:
            raise SocketClosedException('Socket closed')
        return data


    # Send some bytes to socket. Not guaranteed to send all
    # This function raises an exception on timeout.
    def send(self, data):
        # ready = select.select([], [self.socket], [], self.TIMEOUT)[0]
        # if not ready:
        #     # Raise exception on timeout.
        #     raise TimeoutException('writing takes too long')
        return self.socket.send(data)

    # Send all bytes to socket.
    # Underlying send function raises an exception on timeout.
    def sendall(self, data):
        while len(data) > 0:
            sent = self.send(data)
            data = data[sent:]
        return

    # Return the associated socket. 
    def get_socket(self):
        return self.socket
    
    # Read a single line from socket / buffer
    def readline(self, delim='\n', recv_bytes=None):
        if recv_bytes == None:
            recv_bytes = self.read_size

        # check if we have a line available in buffer and return it if so
        pos = self.buffer.find(delim)
        if len(self.buffer) > 0 and pos != -1:
            line = self.buffer[:pos + len(delim)]
            self.buffer = self.buffer[pos + len(delim):]
            return line 

        # Else read it from socket
        data = True
        while data:
            data = self.recv(recv_bytes)
            self.buffer += data

            pos = self.buffer.find(delim)
            if pos != -1:
                line = self.buffer[:pos + len(delim)]
                self.buffer = self.buffer[pos + len(delim):]
                return line 
        return

    # Read whatever data is available
    # Underlying recv helper raises exception on no available data or timeout
    def read(self, recv_bytes=None):
        if recv_bytes == None:
            recv_bytes = self.read_size

        data = ''
        if self.buffer == '':
            # Read directly from the socket.
            data = self.recv(recv_bytes)
        else:
            # Read from the buffer.
            data = self.buffer[:recv_bytes]
            self.buffer = self.buffer[recv_bytes:]

        return data

    # Read exact number of bytes
    # Underlying recv helper raises exception on no available data or timeout
    def read_bytes(self, recv_bytes):
        buflen = len(self.buffer)
        while buflen < recv_bytes:
            # Add to buffer until full enough
            # Read upto defined read_size or remaining bytes whichever is lower
            read_data = self.recv(min(self.read_size, recv_bytes - buflen))
            buflen = buflen + len(read_data)
            self.buffer = self.buffer + read_data

        # Slice data from the buffer.
        data = self.buffer[:recv_bytes]
        self.buffer = self.buffer[recv_bytes:]

        return data
