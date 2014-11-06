# A simple class to hold request / response messages
class Message:
    """ Class to hold request info """
    def __init__(self):
        self.verb = ''
        self.path = ''
        self.version = ''
        self.status = ''
        self.text = ''
        self.headers = {}

    # Helpers for debugging
    def print_request(self, print_headers = False):
        print self.verb, self.path, self.version
        if print_headers:
            for header in self.headers:
                print header + ": " + self.headers[header]
            print ''

    def print_response(self, print_headers = False):
        print self.version, self.status, self.text
        if print_headers:
            for header in self.headers:
                print header + ": " + self.headers[header]
            print ''

