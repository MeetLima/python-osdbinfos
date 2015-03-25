# coding: utf-8
from __future__ import unicode_literals
import os
import sys
import tempfile
import socket

import xmlrpclib
from datetime import datetime, timedelta

import struct

import pkg_resources
from minibelt import json_loads, json_dumps

import logging
logger = logging.getLogger(__name__)

__version__=pkg_resources.require("osdbinfos")[0].version


USER_AGENT = "OsdbInfos v%s" % __version__


TOKEN_EXPIRATION = timedelta(minutes=14)


import httplib
class TimeoutTransport(xmlrpclib.Transport):

    def __init__(self, timeout = 10.0, *args, **kwargs):
        xmlrpclib.Transport.__init__(self, *args, **kwargs)
        self.timeout = timeout

    def make_connection(self, host):
        h = httplib.HTTPConnection(host=host, timeout=self.timeout)
        return h

class OpenSutitlesError(Exception):
    """Generic module errors"""
    pass

class OpenSutitlesTimeoutError(OpenSutitlesError, socket.timeout):
    """ Exception raised when opensubtitle timeouts"""
    pass

class OpenSutitlesInvalidSizeError(Exception):
    """Exceptio nraised when a file is too small"""
    pass


class OpenSutitles(object):
    STATUS_OK = '200 OK'

    url = "http://api.opensubtitles.org/xml-rpc"

    def __init__(self, user='', password='', timeout=10):
        self.token = None
        self.user = user
        self.password = password
        transport = TimeoutTransport(timeout)
        self.server = xmlrpclib.ServerProxy(self.url, transport=transport)
        self.last_query_time = None
        self.state_filename = os.path.join(tempfile.gettempdir(), 'osdbinfos.dat')
        self.load_state()

    def store_state(self):
        """ Store last query time + token to avoid too many registration on OSDB
        """
        state = {
            'last_query_time': self.last_query_time,
            'token': self.token
        }
        with open(self.state_filename, 'w') as fstate:
            fstate.write(json_dumps(state))

    def load_state(self):
        """ Load last_query_time + token from state """
        if os.path.exists(self.state_filename):
            with open(self.state_filename, 'r') as fstate:
                try:
                    state = json_loads(fstate.read())
                    self.last_query_time = state['last_query_time']
                    self.token = state['token']
                except ValueError:
                    logger.debug("Could not deserialize state")

    def is_token_expired(self):
        """ Returns True if the token has expired """
        if self.token is None:
            return True
        if self.last_query_time is None:
            return True
        now = datetime.now()
        if self.last_query_time + TOKEN_EXPIRATION <= now:
            return True
        return False

    def register(self):
        """ Register client on opensubtitles to get token"""
        if self.is_token_expired():
            logger.debug("Registering")
            try:
                result = self.server.LogIn(
                    self.user, self.password, 'en', USER_AGENT
                )
                if result is not None and "token" in result:
                    self.token = result["token"]
            except socket.timeout:
                raise OpenSutitlesTimeoutError()
        else:
            logger.debug("Token do not expires yet, no need for registration")

    def get_hash(self, path):
        """ Return the computed hash to be sent to OS server"""
        logger.debug("Compute hash for path %s", path)
        try:

            longlongformat = b'q'  # long long
            bytesize = struct.calcsize(longlongformat)

            with open(path, "rb") as f:
                filesize = os.path.getsize(path)
                hash = filesize

                if filesize < 65536 * 2:
                    return None

                for x in range(65536 / bytesize):
                    buffer = f.read(bytesize)
                    (l_value,) = struct.unpack(longlongformat, buffer)
                    hash += l_value
                    # to remain as 64bit number
                    hash = hash & 0xFFFFFFFFFFFFFFFF

                f.seek(max(0, filesize - 65536), 0)
                for x in range(65536 / bytesize):
                    buffer = f.read(bytesize)
                    (l_value,) = struct.unpack(longlongformat, buffer)
                    hash += l_value
                    hash = hash & 0xFFFFFFFFFFFFFFFF

                returnedhash = "%016x" % hash
                return returnedhash
        except(IOError, ):
            logger.exception(u"Could not compute hash")
            return None

    def clean_imdbid(self, imdbid):
        imdbid.decode('utf-8')

        if not imdbid.startswith('tt'):
            imdbid = imdbid.rjust(7, b'0')
            imdbid = 'tt' + imdbid
        return imdbid.encode("utf-8")

    def get_infos(self, *movie_hash):
        ret = []

        if len(movie_hash) == 0:
            logger.error("Empty list")
            return ret
        movie_hash = filter(lambda x: x is not None, movie_hash)
        if len(movie_hash) == 0:
            logger.error("List containing only None value")
            return ret

        self.register()
        self.last_query_time = datetime.now()
        logger.debug("Get infos for %s hashes", len(movie_hash))
        try:
            res = self.server.CheckMovieHash(self.token or False, movie_hash)
        except socket.timeout:
            raise OpenSutitlesTimeoutError()

        if res['status'] == self.STATUS_OK:
            for _hash in res['data']:
                result = {}
                datas = res['data'][_hash]
                if len(datas) > 0:
                    result['movie_hash'] = datas.get('MovieHash', None)
                    if "MovieImdbID" in datas:
                        result['imdb_id'] = self.clean_imdbid(
                            datas['MovieImdbID']
                        )
                    kind = result['kind'] = datas.get('MovieKind', None)
                    if kind == "movie":
                        result['movie_name'] = datas.get('MovieName', None)
                        result['movie_year'] = datas.get('MovieYear', None)
                    elif kind == "episode":
                        title = datas["MovieName"]
                        try:
                            result['serie_title'] = title.split('"')[1].strip()
                            result['episode_title'] = title.split('"')[2].strip()
                        except IndexError:
                            pass
                        result['season_number'] = datas.get(
                            'SeriesSeason', None
                        )
                        result['episode_number'] = datas.get(
                            'SeriesEpisode', None
                        )

                        try:
                            result['season_number'] = int(
                                result['season_number']
                            )
                        except (TypeError,):
                            logger.exception("season number was none")
                        except (ValueError,):
                            logger.exception(
                                u"season number was not an integer"
                            )
                        try:
                            result['episode_number'] = int(
                                result['episode_number']
                            )
                        except (TypeError,):
                            logger.exception("episode number was none")
                        except (ValueError,):
                            logger.exception(
                                u"episode number was not an integer"
                            )
                    ret.append(result)
                else:
                    ret.append({'movie_hash': _hash})

        # flatten if multiple entries
        ret = {v['movie_hash']: v for v in ret}
        self.store_state()
        return ret

    def get_files_infos(self, files):
        _hashs_files = {self.get_hash(path): path for path in files}

        _hashs_infos = self.get_infos(*_hashs_files.keys())

        _files_hashes = {
            _hashs_files.get(_hash, None): _hashs_infos.get(_hash, None)
            for _hash in _hashs_infos
        }
        return _files_hashes

def main():
    osdb = OpenSutitles()
    if len(sys.argv) > 1:
        print(json_dumps(osdb.get_files_infos(sys.argv[1:])))
    else:
        print("Please provide one or more path as argument")
        exit(1)

if __name__ == "__main__":
    main()
