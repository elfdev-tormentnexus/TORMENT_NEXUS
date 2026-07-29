"""Tests for consume: what a URL points at, and what it must refuse.

The interesting failures are all quiet ones. A YouTube page fetches fine
and yields a navigation menu. A private address fetches fine and reaches
the router. A server that lies about Content-Length fetches fine and fills
the disk. None of these raise on their own.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import consume  # noqa: E402


class FakeResponse:
    def __init__(self, headers=None, status=200, url="https://example.com/x",
                 blocks=()):
        self.headers = headers or {}
        self.status_code = status
        self.url = url
        self._blocks = list(blocks)

    def iter_content(self, chunk_size=None):
        return iter(self._blocks)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise consume.requests.RequestException(f"HTTP {self.status_code}")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeSession:
    def __init__(self, response):
        self.response = response
        self.calls = []

    def head(self, url, **kwargs):
        self.calls.append(("head", url))
        return self.response

    def get(self, url, **kwargs):
        self.calls.append(("get", url))
        return self.response

    def close(self):
        pass


class MediaDetectionTests(unittest.TestCase):
    """The case the operator named: a watch page is not the recording."""

    def test_youtube_watch_urls_are_media(self):
        for url in (
            "https://www.youtube.com/watch?v=fhHjGwrquDg&list=RDfhHjGwrquDg",
            "https://youtu.be/fhHjGwrquDg",
            "https://music.youtube.com/watch?v=abc",
        ):
            self.assertTrue(consume.is_media_host(url), url)

    def test_other_media_platforms_are_media(self):
        for url in ("https://vimeo.com/12345",
                    "https://soundcloud.com/artist/track",
                    "https://www.twitch.tv/someone"):
            self.assertTrue(consume.is_media_host(url), url)

    def test_an_ordinary_site_is_not_media(self):
        for url in ("https://example.com/paper.pdf",
                    "https://arxiv.org/abs/2301.00001",
                    "https://notyoutube.com/watch"):
            self.assertFalse(consume.is_media_host(url), url)

    def test_a_lookalike_host_is_not_treated_as_youtube(self):
        """Suffix matching must be on a dot boundary, not a substring."""
        self.assertFalse(consume.is_media_host("https://evilyoutube.com/watch"))
        self.assertFalse(consume.is_media_host("https://youtube.com.evil.net/x"))

    def test_media_identification_names_the_missing_tools(self):
        report = consume.identify("https://www.youtube.com/watch?v=x")
        self.assertEqual(report["kind"], "media")
        self.assertIn("yt-dlp", report["reason"])
        self.assertIn("speech-to-text", report["reason"])

    def test_media_is_identified_without_any_network_call(self):
        session = FakeSession(FakeResponse())
        consume.identify("https://youtu.be/x", session=session)
        self.assertEqual(session.calls, [],
                         "a media host must be recognised before fetching")


class SchemeAndAddressTests(unittest.TestCase):
    def test_non_http_schemes_are_refused(self):
        for url in ("file:///etc/passwd", "ftp://host/x", "gopher://host/1"):
            with self.assertRaises(consume.ConsumeError):
                consume.identify(url)

    def test_a_loopback_address_is_refused(self):
        with self.assertRaises(consume.ConsumeError) as caught:
            consume.identify("http://127.0.0.1:8082/v1/embeddings")
        self.assertIn("internal address", str(caught.exception))

    def test_localhost_by_name_is_refused_too(self):
        with self.assertRaises(consume.ConsumeError):
            consume.identify("http://localhost/admin")

    def test_a_private_range_is_refused(self):
        with self.assertRaises(consume.ConsumeError):
            consume.identify("http://192.168.1.1/")

    def test_the_cloud_metadata_address_is_refused(self):
        """169.254.169.254 is the canonical target of this whole class."""
        with self.assertRaises(consume.ConsumeError):
            consume.identify("http://169.254.169.254/latest/meta-data/")

    def test_an_unresolvable_host_is_refused_rather_than_attempted(self):
        with self.assertRaises(consume.ConsumeError):
            consume.identify("http://this-host-does-not-exist.invalid/x")


class ContentTypeTests(unittest.TestCase):
    def _identify(self, content_type, url="https://example.com/thing"):
        session = FakeSession(FakeResponse(
            headers={"Content-Type": content_type, "Content-Length": "10"},
            url=url))
        return consume.identify(url, session=session)

    def test_a_pdf_is_a_document(self):
        report = self._identify("application/pdf")
        self.assertEqual(report["kind"], "document")
        self.assertEqual(report["extension"], ".pdf")

    def test_html_is_a_page_not_a_document(self):
        """The distinction the whole feature turns on."""
        report = self._identify("text/html; charset=utf-8")
        self.assertEqual(report["kind"], "page")

    def test_a_video_content_type_is_media(self):
        report = self._identify("video/mp4")
        self.assertEqual(report["kind"], "media")
        self.assertIn("ffmpeg", report["reason"])

    def test_an_unreadable_type_says_what_is_supported(self):
        report = self._identify("application/x-msdownload")
        self.assertEqual(report["extension"], "")
        self.assertIn(".pdf", report["reason"])

    def test_the_url_extension_is_used_when_the_header_is_vague(self):
        report = self._identify("application/octet-stream",
                                url="https://example.com/manual.epub")
        self.assertEqual(report["extension"], ".epub")


class FetchLimitTests(unittest.TestCase):
    def setUp(self):
        self.folder = os.path.join(
            os.environ.get("TEMP", "."), "consume_test_fetch")

    def test_a_body_that_exceeds_the_ceiling_is_refused_mid_download(self):
        """The server's Content-Length is a claim; the limit is not."""
        session = FakeSession(FakeResponse(
            headers={"Content-Length": "10"},          # the lie
            blocks=[b"x" * 4096] * 40))                # the truth
        with self.assertRaises(consume.ConsumeError) as caught:
            consume.fetch("https://example.com/big.txt", ".txt",
                          folder=self.folder, limit=8192, session=session)
        self.assertIn("ceiling", str(caught.exception))

    def test_nothing_is_left_behind_when_a_download_is_refused(self):
        session = FakeSession(FakeResponse(blocks=[b"y" * 4096] * 10))
        try:
            consume.fetch("https://example.com/big.txt", ".txt",
                          folder=self.folder, limit=4096, session=session)
        except consume.ConsumeError:
            pass
        leftovers = [n for n in os.listdir(self.folder) if n.startswith("big")]
        self.assertEqual(leftovers, [])

    def test_a_normal_body_is_written_whole(self):
        session = FakeSession(FakeResponse(blocks=[b"hello ", b"world"]))
        path, written = consume.fetch("https://example.com/a.txt", ".txt",
                                      folder=self.folder, session=session)
        self.addCleanup(os.remove, path)
        self.assertEqual(written, 11)
        with open(path, "rb") as handle:
            self.assertEqual(handle.read(), b"hello world")

    def test_the_saved_name_cannot_escape_its_folder(self):
        session = FakeSession(FakeResponse(blocks=[b"x"]))
        path, _ = consume.fetch("https://example.com/../../etc/passwd", ".txt",
                                folder=self.folder, session=session)
        self.addCleanup(os.remove, path)
        self.assertEqual(os.path.dirname(os.path.abspath(path)),
                         os.path.abspath(self.folder))


class ConsumeFlowTests(unittest.TestCase):
    def test_a_media_url_stores_nothing(self):
        report = consume.consume("https://www.youtube.com/watch?v=x",
                                 add=lambda path: self.fail("must not store"))
        self.assertIsNone(report["stored"])
        self.assertEqual(report["kind"], "media")

    def test_an_unsupported_type_stores_nothing(self):
        session = FakeSession(FakeResponse(
            headers={"Content-Type": "application/x-msdownload"}))
        report = consume.consume("https://example.com/x.exe",
                                 add=lambda path: self.fail("must not store"),
                                 session=session)
        self.assertIsNone(report["stored"])


if __name__ == "__main__":
    unittest.main()
