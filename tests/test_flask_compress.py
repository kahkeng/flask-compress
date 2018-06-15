import unittest
import os

from flask import Flask, render_template

from flask_compress import Compress


class DefaultsTest(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.testing = True

        Compress(self.app)

    def test_mimetypes_default(self):
        """ Tests COMPRESS_MIMETYPES default value is correctly set. """
        defaults = set(('text/html', 'text/css', 'text/xml', 'application/json',
                        'application/javascript'))
        self.assertEqual(self.app.config['COMPRESS_MIMETYPES'], defaults)

    def test_level_default(self):
        """ Tests COMPRESS_LEVEL default value is correctly set. """
        self.assertEqual(self.app.config['COMPRESS_LEVEL'], 6)

    def test_min_size_default(self):
        """ Tests COMPRESS_MIN_SIZE default value is correctly set. """
        self.assertEqual(self.app.config['COMPRESS_MIN_SIZE'], 500)


class InitTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.testing = True

    def test_constructor_init(self):
        Compress(self.app)

    def test_delayed_init(self):
        compress = Compress()
        compress.init_app(self.app)


class UrlTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.testing = True

        small_path = os.path.join(os.getcwd(), 'tests', 'templates',
                                  'small.html')

        large_path = os.path.join(os.getcwd(), 'tests', 'templates',
                                  'large.html')

        self.small_size = os.path.getsize(small_path) - 1
        self.large_size = os.path.getsize(large_path) - 1

        Compress(self.app)

        @self.app.route('/small/')
        def small():
            return render_template('small.html')

        @self.app.route('/large/')
        def large():
            return render_template('large.html')

    def client_get(self, ufs, encoding):
        client = self.app.test_client()
        response = client.get(ufs, headers=[('Accept-Encoding', encoding)])
        self.assertEqual(response.status_code, 200)
        return response

    def test_compress_level(self):
        """ Tests COMPRESS_LEVEL correctly affects response data. """
        for compress_type in ('gzip', 'brotli'):
            self.app.config['COMPRESS_LEVEL'] = 1
            response = self.client_get('/large/', compress_type)
            response1_size = len(response.data)

            self.app.config['COMPRESS_LEVEL'] = 6
            response = self.client_get('/large/', compress_type)
            response6_size = len(response.data)

            self.assertGreater(response1_size, response6_size)

    def test_brotli_better(self):
        """ Tests that Brotli compresses more than gzip. """
        # For the large.html in 05cb311, gzip actually has a smaller response
        # size for levels 1 and 2: 336 bytes versus 343. Let's just skip past
        # those levels.
        for level in range(3, 10):
            self.app.config['COMPRESS_LEVEL'] = level
            response = self.client_get('/large/', 'gzip')
            response_gzip_size = len(response.data)

            response = self.client_get('/large/', 'brotlin')
            response_brotlin_size = len(response.data)

            self.assertGreater(response_gzip_size, response_brotlin_size)

    def test_compress_min_size(self):
        """ Tests COMPRESS_MIN_SIZE correctly affects response data. """
        for compress_type in ('gzip', 'brotli'):
            response = self.client_get('/small/', compress_type)
            self.assertEqual(self.small_size, len(response.data))

            response = self.client_get('/large/', compress_type)
            self.assertGreater(self.large_size, len(response.data))

    def test_mimetype_mismatch(self):
        """ Tests if mimetype not in COMPRESS_MIMETYPES. """
        for compress_type in ('gzip', 'brotli'):
            response = self.client_get('/static/1.png', compress_type)
            self.assertEqual(response.mimetype, 'image/png')

    def test_content_length_options(self):
        client = self.app.test_client()
        for compress_type in ('gzip', 'brotli'):
            headers = [('Accept-Encoding', compress_type)]
            response = client.options('/small/', headers=headers)
            self.assertEqual(response.status_code, 200)

    def test_constants(self):
        self.assertEqual(len(Compress.CONTENT_ENCODINGS), 2)
        self.assertEqual(
                len(Compress.CONTENT_ENCODINGS),
                max(Compress.GZIP, Compress.BROTLI) + 1)
        self.assertEqual(Compress.CONTENT_ENCODINGS[Compress.GZIP], 'gzip')
        self.assertEqual(Compress.CONTENT_ENCODINGS[Compress.BROTLI], 'brotli')

if __name__ == '__main__':
    unittest.main()
