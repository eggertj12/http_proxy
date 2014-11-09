import re
import datetime
import email.utils as eut
import sys

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
        self.cache_file = None

    # Read request data from SocketReader
    def parse_request(self, reader):
#        print "reading line"
        line = reader.readline().strip('\r\n')
#        print "read line:", line
        try:
            self.verb, URI, self.version = line.split(" ")
        except Exception, e:
            print "Invalid request line: ", line

        self.verb = self.verb.upper()

        # Use this from given solution, better than the mess I had before
        match = re.match('(http://)?([^/:]*)(:[0-9]*)?(/.*)?',URI)
        if match == None:
            print "Invalid request URI:", URI
        self.scheme = match.group(1)
        self.hostname = match.group(2)
        self.port = match.group(3)
        self.path = match.group(4)
        # default scheme to http if not available
        if self.scheme == None:
            self.scheme = 'http://'
        # default port is 80, if no port is given
        if self.port ==  None:
            self.port = 80
        else:
            self.port = int(self.port.strip(':'))
        # default path is /, if no path is given
        if self.path == None:
            self.path = '/'

        self.parse_headers(reader)

    # Read response data from SocketReader
    def parse_response(self, reader):
        line = reader.readline().strip('\r\n')
        try:
            self.version, self.status, self.text = line.split(" ", 2)
        except Exception:
            print "Invalid response line: ", line

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


    # Determine cacheability of request
    def _is_cacheable_request(self):
        if self.verb.upper() != 'GET':
            return False
        if 'authorization' in self.headers:
            return False
        if 'cache-control' in self.headers:
            cc = self.headers['cache-control'].lower()
            if 'no-store' in cc or 'no-cache' in cc:
                return False
        # Nothing obvious preventing this request from cache
        return True

    # Determine cacheability of response
    def _is_cacheable_response(self):
        if self.status != '200':
            return False
        if 'cache-control' in self.headers:
            cc = self.headers['cache-control'].lower()
            if 'no-store' in cc or 'no-cache' in cc or 'private' in cc:
                return False
            if 'max-age' in cc or 's-maxage' in cc:
                return True
        
        if 'expires' in self.headers:
            return True

        # Default to caching even when not explicitly forbidden
        return True

    # Is this a cache-able message
    def is_cacheable(self):
        msg = ''
        if self.verb != '':
            # Is a request
            return self._is_cacheable_request()
        elif self.status != '':
            # Is a response
            return self._is_cacheable_response()
        return False


    # Calculate freshness date of response
    def cache_expiry_date(self):
        # Get response date
        if 'date' in self.headers:
            date = self._parsedate(self.headers['date'])
        else:
            date = datetime.datetime.now()

        # max-age takes precedence over expires
        if 'cache-control' in self.headers:
            match = re.match('.*s-maxage=(\d+).*', self.headers['cache-control'])
            if match != None:
                return date + datetime.timedelta(0, int(match.group(1)))

            match = re.match('.*max-age=(\d+).*', self.headers['cache-control'])
            if match != None:
                return date + datetime.timedelta(0, int(match.group(1)))

        if 'expires' in self.headers:
            return self._parsedate(self.headers['expires'])

        # Simple custom heuristics, just cache for one day
        return date + datetime.timedelta(1, 0)

    # Parse a date string into datetime object
    def _parsedate(self, text):
        return datetime.datetime(*eut.parsedate(text)[:6])

    # Helper for debugging
    def print_message(self, print_headers = False):
        if print_headers:
            print self._message_to_string()
            print self._headers_to_string()
        else:
            print self._message_to_string().strip('\r\n')

    def __str__(self):
        self.to_string()

