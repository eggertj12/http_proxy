import re

# A class to hold request / response messages
class Message:
    """ Class to hold request info """
    def __init__(self):
        self.scheme = ''
        self.hostname = ''
        self.verb = ''
        self.path = ''
        self.version = ''
        self.status = ''
        self.text = ''
        self.headers = {}

    # Read request data from SocketReader
    def parse_request(self, reader):
#        print "reading line"
        line = reader.readline().strip('\r\n')
#        print "read line:", line
        try:
            self.verb, URI, self.version = line.split(" ")
        except Exception, e:
            print >> sys.stderr, "Invalid request line: ", e.strerror

        self.verb = self.verb.upper()

        # Use this from given solution, better than the mess I had before
        match = re.match('(http://)([^/:]*)(:[0-9]*)?(/.*)?',URI)
        if match == None:
            print >> sys.stderr, "Invalid request URI: ", e.strerror
            print >> sys.stderr, "URI: ", URI
        self.scheme = match.group(1)
        self.hostname = match.group(2)
        self.port = match.group(3)
        self.path = match.group(4)
        # default port is 80, if no port is given
        if self.port ==  None:
            self.port = 80
        else:
            self.port = int(self.port)
        # default path is /, if no path is given
        if self.path == None:
            self.path = '/'

        self.parse_headers(reader)

    # Read response data from SocketReader
    def parse_response(self, reader):
        line = reader.readline().strip('\r\n')
        try:
            self.version, self.status, self.text = line.split(" ", 2)
        except Exception, e:
            print "Invalid response line: ", e.message

        self.parse_headers(reader)

    # Read header lines from SocketReader and add to headers dictionary
    def parse_headers(self, reader):
        line = reader.readline().strip('\r\n')
        while len(line) > 0:
            split = line.split(':', 1)
            if len(split) != 2:
                raise Exception('Invalid header read')

            key = split[0].lower()
            value = split[1]
            self.headers[key] = value
            line = reader.readline().strip('\r\n')
            

    # Concat the headers to a \r\n delimited string
    def _headers_to_string(self):
        hdrs = ''
        for header in self.headers:
            hdrs = hdrs +  header + ": " + self.headers[header] + "\r\n"
        return hdrs


    # Build the message line
    def _message_to_string(self):
        msg = ''
        if self.verb != '':
            # Is a request
            msg = self.verb + " " + self.path + " " + self.version + "\r\n"
        elif self.status != '':
            # Is a response
            msg = self.version + " " + self.status + " " + self.text + "\r\n"
        else:
            raise Exception('Invalid message object')

        return msg

    # Build a string ready to send to socket from the message line and headers
    def to_string(self):
        msg = self._message_to_string()
        msg = msg + self._headers_to_string()
        msg = msg + "\r\n"
        return msg


    # Determine if sender is requesting persistent connection
    def is_persistent(self):
        # HTTP/1.1 is persistent unless connection: close header is sent
        if (self.version == 'HTTP/1.1'):
            if ('connection' in self.headers) and ('close' in self.headers['connection'].lower()):
                return False

        # HTTP/1.0 is not persistent unless connection: keep-alive header is sent
        elif (self.version == 'HTTP/1.0'):        
            if not ('connection' in self.headers and 'keep-alive' in self.headers['connection'].lower()):
                return False

        # Assume it is persistent since we have not found otherwise
        return True


    # Check if headers indicate data in message
    def has_content(self):
        if 'content-length' in self.headers:
            return "content-length"

        elif 'transfer-encoding' in self.headers:
            tf_encoding = self.headers['transfer-encoding']
            if "chunked" in tf_encoding.lower():
                return "chunked"
        return None


    # Add required via header
    def add_via(self, name='p-p-p-proxy'):
        # Add required via header
        if self.version[:5] == 'HTTP/':
            ver = self.version[5:]
        else:
            ver = self.version
        if 'via' in self.headers:
            self.headers['via'] += ', ' + ver + ' ' + name
        else:
            self.headers['via'] = ver + ' ' + name


    # Helper for debugging
    def print_message(self, print_headers = False):
        if print_headers:
            print self._message_to_string()
            print self._headers_to_string()
        else:
            print self._message_to_string().strip('\r\n')

    def __str__(self):
        self.to_string()

