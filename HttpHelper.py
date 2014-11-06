from urlparse import urlsplit
from socket import *
import socket

from Message import Message

# Helper to parse http messages
class HttpHelper:
    BUFLEN = 4096

    # Get the first line of a request and split into parts
    @staticmethod
    def parse_request_line(s):
        req = Message()
        sp = s.readline().strip('\r\n')

        req.verb, req.path, req.version = sp.split(" ")
        o = urlsplit(req.path)
        req.path = o.path
        if len(o.query) > 0:
            req.path += "?" + o.query
        if len(o.fragment) > 0:
            req.path += "#" + o.fragment
        return req

    # Get the first line of a response and split into parts
    @staticmethod
    def parse_response_line(s):
        resp = Message()
        sp = s.readline().strip('\r\n')

        resp.version, resp.status, resp.text = sp.split(" ", 2)
        return resp

    # Read the headers line by line and store in dictionary
    @staticmethod
    def parse_headers(s, message):
        line = s.readline().strip('\r\n')
        print "line: ", line
        while len(line) > 0:
            split = line.split(':', 1)
            if len(split) != 2:
                raise IOError('Invalid header read')

            key = split[0].lower()
            value = split[1]
            message.headers[key] = value.strip(" \n\r\t")
            line = s.readline().strip('\r\n')
            
        return message

    # Parse host value for port number. Defaults to 80 on not found
    @staticmethod
    def get_dest_port(req):
        if ':' in req.headers['host']:
            req.headers['host'], req.port = req.headers['host'].split(':')
        else:
            req.port = '80'
        return

    # Rebuild the request to send to server
    @staticmethod
    def request_to_string(req):
        request = req.verb + " " + req.path + " " + req.version + "\r\n"
        for header in req.headers:
            request += header + ": " + req.headers[header] + "\r\n"
        request = request + "\r\n"
        return request

    # Rebuild the response received to send back to client
    @staticmethod
    def response_to_string(resp):
        response = resp.version + " " + resp.status + " " + resp.text + "\r\n"
        for header in resp.headers:
            response += header + ": " + resp.headers[header] + "\r\n"
        response = response + "\r\n"
        return response

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
    def read_content_length(reading, writing, length):
        read = 0
        while read < length:
            response = reading.recv(min(HttpHelper.BUFLEN, length - read))
            read = read + len(response)
            writing.sendall(response)

    # Read data sent via chunked transfer-encoding
    @staticmethod
    def read_chunked(reading, writing):
        chunk_line = reading.readline()
        size = int(chunk_line.split(";", 1)[0], 16)

        # Loop while there are chunks
        while size > 0:
            print "Serving chunk of size: ", size
            # Start by sending the chunk size
            print "Chunk_line: ", chunk_line, " Size: ", len(chunk_line)
            writing.sendall(chunk_line)

            read = 0
            while read < size + 2:
                response = reading.recv(min(HttpHelper.BUFLEN, size + 2 - read))
                read = read + len(response)
                writing.sendall(response)

            # Try to read next chunk line, fall back to size zero in case server does not send terminating chunk
            chunk_line = reading.readline()

            # # Read again on 0 length which can be caused by terminating \r\n of chunk data
            # if len(chunk_line) == 0:
            #     chunk_line = reading.readline()

            if len(chunk_line) > 0:
                size = int(chunk_line.split(";", 1)[0], 16)
            else:
                size = 0
                chunk_line = ''

        # Send final 0 size chunk to recipient
        writing.sendall(chunk_line)

        # Read trailer-part and forward it blindly
        line = reading.readline()
        while len(line) > 2:
            # Most likely the connection has been closed by now
            # but there could be more to come
            try:
                writing.sendall(line)
            except socket.error, e:
                pass

            line = reading.readline()
        return
