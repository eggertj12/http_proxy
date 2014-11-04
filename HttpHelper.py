from urlparse import urlsplit

from Message import Message

# Helper to parse http messages
class HttpHelper:

    # Get the first line of a request and split into parts
    @staticmethod
    def parse_request_line(s):
        req = Message()
        sp = s.readline()
        # print "request_line: ", sp
        req.verb, req.path, req.version = sp.split(" ")
        o = urlsplit(req.path)
        req.path = o.path
        if len(o.query) > 0:
            req.path += "?" + o.query
        if len(o.fragment) > 0:
            req.path += "#" + o.fragment
        return req

    # Read the headers line by line and store in dictionary
    @staticmethod
    def parse_headers(s, req):
        line = s.readline()
        while len(line) > 0:
            split = line.split(':', 1)
            if len(split) != 2:
                raise IOError('Invalid header read')

            key = split[0].lower()
            value = split[1]
            req.headers[key] = value.strip(" \n\r\t")
            line = s.readline()
            
        return req
