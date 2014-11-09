import urllib
import email.utils as eut
import os
import datetime

from Message import Message

# Helper to parse http messages
class Cache:
    CACHE_FOLDER = 'cache/'

    # Create cache filename, and create folder if not already existing
    @staticmethod
    def filename(url, filename, expire_date, content_type):
        my_dir = Cache.CACHE_FOLDER + str(url)

        ExpireDate = str(expire_date)
        if ExpireDate == 'None':
            return None

        print ExpireDate
        strippedDate = str(datetime.datetime.strptime(expire_date, "(%Y, %m, %d, %H, %M, %S, 0, 1, -1)"))
        print strippedDate
        date = str.replace(str.replace(str.replace(strippedDate, ':', ''), ' ', ''), '-', '')
        lock = threading.Lock()
        with lock:
            if not os.path.exists(my_dir):
                os.makedirs(my_dir)

        filename = filename.split("?")[0] + '|' + content_type

        return my_dir + '/' + date + urllib.quote_plus(filename)


    #Saving data to cache
    @staticmethod
    def cache_file(filename, data):
        lock = threading.Lock()
        with lock:
            file = open(filename, "ab+")
            file.write(data)
            file.close()


    #Check if data is on proxy
    @staticmethod
    def is_in_cache(url, filename):
        lock = threading.Lock()
        mypath = Cache.CACHE_FOLDER + str(url) + '/'
        with lock:
            if not os.path.exists('cache'):
                os.makedirs('cache')
            if not os.path.exists(self.CACHE_FOLDER + url):
                return None

            searchfile = urllib.quote_plus(filename)

            for file in os.listdir(mypath):
                s_file = file.split('%7C')[0]
                if s_file.endswith(searchfile):
                    currenttime = datetime.datetime.now()
                    filetime = datetime.datetime.strptime(str(s_file)[0:14], "%Y%m%d%H%M%S")
                    if currenttime < filetime:
                        myfile = mypath + file
                        return myfile
                    else:
                        #If the file is expired it is thrown away
                        os.remove(mypath + file)

            #searchfile = urllib.quote_plus(filename)[:29]

            # for file in os.listdir(myPath):
            #     if file.endswith(searchfile):
            #         currenttime = datetime.datetime.now()
            #         filetime = datetime.datetime.strptime(str(file)[1:20], "%Y_%m_%d_%H_%M_%S")
            #         if currenttime < filetime:
            #             myfile = open(myPath + str(file), 'r')
            #             content  = myfile.read()
            #             myfile.close()
            #             return content

            return None

    # Serve a file from cache
    @staticmethod
    def send_cached_file(myfile, writing):
        read = 0
        #filestat = os.stat(myfile)
        #filelength = filestat.st_size
        currfile = open(myfile,'r')

        filelength = os.path.getsize(myfile)
        content_type = urllib.unquote_plus(myfile).split('|')[-1]

        my_header = 'HTTP/1.1 200 OK\r\n'
        my_header += 'content-type: ' + content_type + '\r\n'
        my_header += 'content-length: ' + str(filelength) + '\r\n\r\n'
        writing.sendall(my_header)

        while read < filelength:
            response = currfile.read(buflen)
            read = read + len(response)
            writing.sendall(response)
        currfile.close()
