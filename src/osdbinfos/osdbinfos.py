# coding: utf-8
import os
import sys
import tempfile
import socket

try:
    # python 2
    import xmlrpclib
    import httplib
except ImportError:
    # python 3
    import xmlrpc.client as xmlrpclib
    import http.client as httplib

from datetime import datetime, timedelta

import struct

import pkg_resources
import json

import logging
logger = logging.getLogger(__name__)

__version__ = pkg_resources.require("osdbinfos")[0].version

USER_AGENT = "OsdbInfos v%s" % __version__

TOKEN_EXPIRATION = timedelta(minutes=14)


class TimeoutTransport(xmlrpclib.Transport):
    def __init__(self, timeout=10.0, *args, **kwargs):
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


class OpenSutitlesInvalidSizeError(OpenSutitlesError):
    """Exceptio nraised when a file is too small"""
    pass


class OpenSutitlesServiceUnavailable(OpenSutitlesError):
    pass


class OpenSutitlesInvalidParam(OpenSutitlesError, ValueError):
    pass


class OpenSutitlesNetworkError(OpenSutitlesError):
    pass


class UnauthorizedOpenSutitlesError(OpenSutitlesError):
    pass


class MandatoryParameterMissing(OpenSutitlesError):
    pass


class NoSessionOpenSubtitlesError(OpenSutitlesError):
    pass


class DownloadLimitReachedOpenSutitleError(OpenSutitlesError):
    pass


class InvalidParametersOpenSutitlesError(OpenSutitlesError):
    pass


class MethodNotFoundOpenSutitlesError(OpenSutitlesError):
    pass


class UnknownOpenSubtitlesError(OpenSutitlesError):
    pass


class InvalidUserAgentOpenSubtitlesError(OpenSutitlesError):
    pass


class DisabledUserAgentOpenSubtitlesError(OpenSutitlesError):
    pass


class InvalidResultOpenSutitlesError(OpenSutitlesError):
    pass


ERROR_STATUS_EXCEPTIONS = {
    '401': UnauthorizedOpenSutitlesError,
    '405': MandatoryParameterMissing,
    '406': NoSessionOpenSubtitlesError,
    '407': DownloadLimitReachedOpenSutitleError,
    '408': InvalidParametersOpenSutitlesError,
    '409': MethodNotFoundOpenSutitlesError,
    '410': UnknownOpenSubtitlesError,
    '411': InvalidUserAgentOpenSubtitlesError,
    '415': DisabledUserAgentOpenSubtitlesError,
}


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
        self.state_filename = os.path.join(tempfile.gettempdir(),
                                           'osdbinfos.dat')
        self.load_state()

    def store_state(self):
        """ Store last query time + token to avoid too many registration on OSDB
        """
        state = {'last_query_time': self.last_query_time.timestamp(),
                 'token': self.token}
        with open(self.state_filename, 'w') as fstate:
            fstate.write(json.dumps(state))

    def load_state(self):
        """ Load last_query_time + token from state """
        if os.path.exists(self.state_filename):
            with open(self.state_filename, 'r') as fstate:
                try:
                    state = json.loads(fstate.read())
                    self.last_query_time = datetime.fromtimestamp(
                        state['last_query_time'])
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
                result = self.server.LogIn(self.user, self.password, 'en',
                                           USER_AGENT)
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

                for x in range(int(65536 / bytesize)):
                    buffer = f.read(bytesize)
                    (l_value, ) = struct.unpack(longlongformat, buffer)
                    hash += l_value
                    # to remain as 64bit number
                    hash = hash & 0xFFFFFFFFFFFFFFFF

                f.seek(max(0, filesize - 65536), 0)
                for x in range(int(65536 / bytesize)):
                    buffer = f.read(bytesize)
                    (l_value, ) = struct.unpack(longlongformat, buffer)
                    hash += l_value
                    hash = hash & 0xFFFFFFFFFFFFFFFF

                returnedhash = "%016x" % hash
                return returnedhash
        except (IOError, ):
            logger.exception(u"Could not compute hash")
            return None

    def clean_imdbid(self, imdbid):
        if not imdbid.startswith('tt'):
            imdbid = imdbid.rjust(7, '0')
            imdbid = 'tt' + imdbid
        return imdbid

    def get_infos(self, *movie_hash):

        ret = {}

        if len(movie_hash) == 0:
            logger.error("Empty list")
            return ret
        movie_hash = list(filter(lambda x: x is not None, movie_hash))
        if len(movie_hash) == 0:
            logger.error("List containing only None value")
            return ret

        try:
            self.register()
            self.last_query_time = datetime.now()
            logger.debug("Get infos for %s hashes", len(movie_hash))
            res = self.server.CheckMovieHash(self.token or False, movie_hash)
        except socket.timeout:
            raise OpenSutitlesTimeoutError()
        except xmlrpclib.ProtocolError as e:
            if e.errcode == 503:
                raise OpenSutitlesServiceUnavailable()
            else:
                raise OpenSutitlesError(e)
        except socket.error as e:
            raise OpenSutitlesNetworkError(str(e))
        except Exception as e:
            raise OpenSutitlesError(str(e))

        if res['status'] == self.STATUS_OK:
            datas = res['data']
            if isinstance(datas, dict):
                # normal case
                return self._parse_dict(datas)
            elif isinstance(datas, list):
                # osdb gave us a list, which is not what is expected.
                # transform the list in a dictionary and parse it as expected
                # we check the type of items
                datas = {x['MovieHash']: x for x in datas if isinstance(x, dict)}
                return self._parse_dict(datas)
            else:
                return InvalidResultOpenSutitlesError("Can't parse %s" % type(datas))
        else:
            status = res['status']
            if status:
                status_code = res['status'].split(" ")[0]
                if status_code in ERROR_STATUS_EXCEPTIONS:
                    # raise exception with original message
                    raise ERROR_STATUS_EXCEPTIONS[status_code](res['status'])
                else:
                    raise OpenSutitlesError(res['status'])
            else:
                raise OpenSutitlesError("Unknown error (%s)" % status_code)

    def _parse_dict(self, datas):
        """Parse osdb result as a dict"""
        ret = []
        for _hash in datas:
            result = {}
            datas = datas[_hash]
            if len(datas) > 0:
                result['movie_hash'] = datas.get('MovieHash', None)
                if "MovieImdbID" in datas:
                    result['imdb_id'] = self.clean_imdbid(datas['MovieImdbID'])
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
                    result['season_number'] = datas.get('SeriesSeason', None)
                    result['episode_number'] = datas.get('SeriesEpisode', None)

                    try:
                        result['season_number'] = int(result['season_number'])
                    except (TypeError, ):
                        logger.exception("season number was none")
                    except (ValueError, ):
                        logger.exception(u"season number was not an integer")
                    try:
                        result['episode_number'] = int(
                            result['episode_number'])
                    except (TypeError, ):
                        logger.exception("episode number was none")
                    except (ValueError, ):
                        logger.exception(u"episode number was not an integer")
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

        _files_hashes = {}
        if _hashs_infos:
            _files_hashes = {
                _hashs_files.get(_hash, None): _hashs_infos.get(_hash, None)
                for _hash in _hashs_infos
            }
        return _files_hashes

    def insert_movie_hash(self, hashes):
        """ Call xmlrpc.InsertMovieHash
        :param hashes: list of dict containing at leat imdbid, moviehash, moviebytesize
        :return: return the data  field from osdb response
        """

        # refformat imdbids
        for data in hashes:
            try:
                data['imdbid'] = data['imdbid'].replace('tt', '')
            except KeyError:
                raise OpenSutitlesInvalidParam("Key imdbid is missing")

        try:
            self.register()
            self.last_query_time = datetime.now()
            logger.debug("Insert %s hashes", len(hashes))
            res = self.server.InsertMovieHash(self.token or False, hashes)
        except socket.timeout:
            raise OpenSutitlesTimeoutError()
        except xmlrpclib.ProtocolError as e:
            logger.exception("xmlrpc error")
            if e.errcode == 503:
                raise OpenSutitlesServiceUnavailable()
            else:
                raise OpenSutitlesError(e)
        except Exception as e:
            logger.exception("unknown error")
            raise OpenSutitlesError(e)

        if '408' in res['status']:
            raise OpenSutitlesInvalidParam('Invalid parameters')

        if res['status'] == self.STATUS_OK:
            result = res['data']
            return result


def main():
    osdb = OpenSutitles()
    if len(sys.argv) > 1:
        print(json.dumps(osdb.get_files_infos(sys.argv[1:])))
    else:
        print("Please provide one or more path as argument")
        exit(1)


if __name__ == "__main__":
    main()
