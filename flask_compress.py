
# Authors: William Fagan
# Copyright (c) 2013-2017 William Fagan
# License: The MIT License (MIT)

import brotli
import copy
import sys
import zlib
from gzip import GzipFile
from io import BytesIO

from flask import request, current_app


if sys.version_info[:2] == (2, 6):
    class GzipFile(GzipFile):
        """ Backport of context manager support for python 2.6"""
        def __enter__(self):
            if self.fileobj is None:
                raise ValueError("I/O operation on closed GzipFile object")
            return self

        def __exit__(self, *args):
            self.close()


class DictCache(object):

    def __init__(self):
        self.data = {}

    def get(self, key):
        return self.data.get(key)

    def set(self, key, value):
        self.data[key] = value


class Compress(object):
    """
    The Compress object allows your application to use Flask-Compress.

    When initialising a Compress object you may optionally provide your
    :class:`flask.Flask` application object if it is ready. Otherwise,
    you may provide it later by using the :meth:`init_app` method.

    :param app: optional :class:`flask.Flask` application object
    :type app: :class:`flask.Flask` or None
    """
    BROTLI = 0
    GZIP = 1
    CONTENT_ENCODINGS = ('brotli', 'gzip')
    TEXT_TYPES = set(('text/html', 'text/css', 'text/xml', 'application/json',
                      'application/javascript'))

    def __init__(self, app=None):
        # type: (flask.Flask) -> None
        """
        An alternative way to pass your :class:`flask.Flask` application
        object to Flask-Compress. :meth:`init_app` also takes care of some
        default `settings`_.

        :param app: the :class:`flask.Flask` application object.
        """
        self.app = app
        if app is not None:
            self.init_app(app)
        self._compress_methods = (self._brotli_compress, self._gzip_compress)

    def init_app(self, app):
        # type: (flask.Flask) -> None
        defaults = [
            ('COMPRESS_MIMETYPES', copy.deepcopy(self.TEXT_TYPES)),
            ('COMPRESS_LEVEL', 6),
            ('COMPRESS_MIN_SIZE', 500),
            ('ENABLE_GZIP', True),
            ('ENABLE_BROTLI', True),
            ('GZIP_COMPRESS_CACHE_KEY', None),
            ('BROTLI_COMPRESS_CACHE_KEY', None),
            ('COMPRESS_CACHE_BACKEND', None),
            ('COMPRESS_REGISTER', True),
        ]

        for k, v in defaults:
            app.config.setdefault(k, v)

        backend = app.config['COMPRESS_CACHE_BACKEND']
        self._cache = backend() if backend else None
        self._gzip_cache_key = app.config['GZIP_COMPRESS_CACHE_KEY']
        self._brotli_cache_key = app.config['BROTLI_COMPRESS_CACHE_KEY']
        self._cache_keys = (self._brotli_cache_key, self._gzip_cache_key)

        if (app.config['COMPRESS_REGISTER'] and
                app.config['COMPRESS_MIMETYPES']):
            app.after_request(self.after_request)

    def after_request(self, response):
        # type: (flask.Response) -> flask.Response
        app = self.app or current_app
        accept_encoding = request.headers.get('Accept-Encoding', '')

        if (response.mimetype not in app.config['COMPRESS_MIMETYPES'] or
            not 200 <= response.status_code < 300 or
            response.content_length is None or
            response.content_length < app.config['COMPRESS_MIN_SIZE'] or
            'Content-Encoding' in response.headers):
            return response

        encoding = None
        # Default to Brotli if both are available
        if app.config['ENABLE_BROTLI'] and 'brotli' in accept_encoding.lower():
            encoding = self.BROTLI
        elif app.config['ENABLE_GZIP'] and 'gzip' in accept_encoding.lower():
            encoding = self.GZIP

        if encoding is None:
            return response

        response.direct_passthrough = False

        if self._cache is not None:
            key = self._cache_keys[encoding](response)
            compressed_content = (
                self._cache.get(key) or
                self._compress_methods[encoding](app, response)
            )
            self._cache.set(key, compressed_content)
        else:
            compressed_content = self._compress_methods[encoding](app, response)

        response.set_data(compressed_content)

        response.headers['Content-Encoding'] = self.CONTENT_ENCODINGS[encoding]
        response.headers['Content-Length'] = response.content_length

        vary = response.headers.get('Vary')
        if vary:
            if 'accept-encoding' not in vary.lower():
                response.headers['Vary'] = '{}, Accept-Encoding'.format(vary)
        else:
            response.headers['Vary'] = 'Accept-Encoding'

        return response

    def _gzip_compress(self, app, response):
        # type: (flask.Flask, flask.Response) -> bytes
        gzip_buffer = BytesIO()
        # Brotli's max compression goes to 11, but zlib only goes to 9
        level = min(zlib.Z_BEST_COMPRESSION, app.config['COMPRESS_LEVEL'])
        with GzipFile(mode='wb',
                      compresslevel=app.config['COMPRESS_LEVEL'],
                      fileobj=gzip_buffer) as gzip_file:
            gzip_file.write(response.get_data())
        return gzip_buffer.getvalue()

    def _brotli_compress(self, app, response):
        # type: (flask.Flask, flask.Response) -> bytes
        if response.mimetype in self.TEXT_TYPES:
            mode = brotli.MODE_TEXT
        else:
            mode = brotli.MODE_GENERIC
        return brotli.compress(response.get_data(),
                               mode,
                               app.config['COMPRESS_LEVEL'])
