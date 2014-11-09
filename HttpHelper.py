from urlparse import urlsplit
from socket import *
import socket

from Message import Message
from Cache import Cache

# Helper to parse http messages
class HttpHelper:
    BUFLEN = 4096

    # Create a response to answer client, f.ex. in case of error
    @staticmethod
    def create_response(status, message):
        # set up a Message object for the logger
        resp = Message()
        resp.version = 'HTTP/1.1'
        resp.status = status
        resp.text = message
        return resp

    # Read data sent via buffered mode
    @staticmethod
    def read_content_length(reading, writing, length, cache_file = None):
        read = 0
        while read < length:
            response = reading.read(min(HttpHelper.BUFLEN, length - read))
            read = read + len(response)
            writing.sendall(response)
            if cache_file != None:
                Cache.cache_file(cache_file, response)

    # Read data sent via chunked transfer-encoding
    @staticmethod
    def read_chunked(reading, writing, cache_file = None):
        chunk_line = reading.readline()
        size = int(chunk_line.split(";", 1)[0], 16)

        # Loop while there are chunks
        while size > 0:
            # print "Serving chunk of size: ", size
            # Start by sending the chunk size
            writing.sendall(chunk_line)

            read = 0
            while read < size + 2:
                response = reading.read(min(HttpHelper.BUFLEN, size + 2 - read))
                read = read + len(response)
                writing.sendall(response)
                if cache_file != None:
                    Cache.cache_file(cache_file, response)

            # Try to read next chunk line, fall back to size zero in case server does not send terminating chunk
            chunk_line = reading.readline()

            if len(chunk_line) > 0:
                size = int(chunk_line.split(";", 1)[0], 16)
            else:
                size = 0
                chunk_line = ''

        # Send final 0 size chunk to recipient
        writing.sendall(chunk_line)
        # print "Serving final chunk of size: ", size

        # Read trailer-part and forward it blindly
        line = reading.readline()
        while len(line) > 2:
            print "Sending a line from trailer-part:", line
            # Most likely the connection has been closed by now
            # but there could be more to come
            try:
                writing.sendall(line)
            except socket.error, e:
                print "Socket closed on writing chunk trailer"
                pass

            line = reading.readline()

        # Send final empty line
        writing.sendall(line)

        return



