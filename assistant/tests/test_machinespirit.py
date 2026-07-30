"""Tests for the anchor dictionary and the two servers it depends on.

The properties here are the ones that fail silently rather than loudly. A
wrong section slice returns real vectors under the wrong words; a truncated
trajectory has the same shape as a complete one; a pooled-server outage
reported as an unpooled one sends the operator to restart the wrong
process. None of those raise, and all of them produce a fluent account of
something that did not happen.
"""
import json
import math
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core import machinespirit as ms  # noqa: E402


class DictionaryTests(unittest.TestCase):
    def setUp(self):
        self.version = ms.ANCHOR_VERSION
        ms.reset_cache()

    def tearDown(self):
        ms.ANCHOR_VERSION = self.version
        ms.reset_cache()

    def test_v2_carries_v1s_core_unchanged(self):
        """The whole point of v2's shape: v1 stones stay comparable."""
        here = os.path.dirname(os.path.abspath(ms.__file__))
        with open(os.path.join(here, "anchors_v1.json"), encoding="utf-8") as fh:
            v1 = json.load(fh)
        with open(os.path.join(here, "anchors_v2.json"), encoding="utf-8") as fh:
            v2 = json.load(fh)
        self.assertEqual(v1["core"], v2["core"])
        self.assertEqual(v1["project"], v2["project"])
        self.assertEqual(v1["core_digest"], v2["core_digest"])
        self.assertEqual(v1["project_digest"], v2["project_digest"])

    def test_digest_matches_the_list_it_names(self):
        """A digest that is not recomputed is decoration."""
        import hashlib

        for version in ("1", "2"):
            ms.ANCHOR_VERSION = version
            ms.reset_cache()
            with open(ms.anchors_file(), encoding="utf-8") as fh:
                data = json.load(fh)
            for section in ("core", "project", "life"):
                texts = data.get(section)
                if not texts:
                    continue
                digest = hashlib.sha256()
                for text in texts:
                    digest.update(text.encode("utf-8"))
                    digest.update(b"\x00")
                self.assertEqual(
                    digest.hexdigest(), data[f"{section}_digest"],
                    f"v{version} {section} digest does not match its list")

    def test_v1_has_no_life_section_and_does_not_invent_one(self):
        ms.ANCHOR_VERSION = "1"
        ms.reset_cache()
        self.assertEqual(ms.dictionary()["life"], 0)
        self.assertEqual(len(ms.anchor_texts(True, True)), 138)

    def test_v2_adds_life_without_disturbing_the_earlier_order(self):
        ms.ANCHOR_VERSION = "2"
        ms.reset_cache()
        v2 = ms.anchor_texts(True, True)
        ms.ANCHOR_VERSION = "1"
        ms.reset_cache()
        v1 = ms.anchor_texts(True, True)
        self.assertEqual(v2[:len(v1)], v1,
                         "v2 must extend v1's order, not rearrange it")

    def test_no_anchor_appears_twice(self):
        """A repeated anchor is two dimensions that cannot disagree."""
        for version in ("1", "2"):
            ms.ANCHOR_VERSION = version
            ms.reset_cache()
            texts = ms.anchor_texts(True, True)
            self.assertEqual(len(texts), len(set(texts)),
                             f"v{version} has a duplicate anchor")

    def test_switching_version_reloads_rather_than_serving_the_old_one(self):
        ms.ANCHOR_VERSION = "1"
        first = len(ms.anchor_texts(True, True))
        ms.ANCHOR_VERSION = "2"
        second = len(ms.anchor_texts(True, True))
        self.assertGreater(second, first)


class SectionSelectionTests(unittest.TestCase):
    """Selecting sections must take the same ones from texts and vectors."""

    def setUp(self):
        self.version = ms.ANCHOR_VERSION
        ms.ANCHOR_VERSION = "2"
        ms.reset_cache()
        self.book = ms.dictionary()

    def tearDown(self):
        ms.ANCHOR_VERSION = self.version
        ms.reset_cache()

    def _labelled(self, include_project, include_life):
        """Stand-in vectors that carry their own index, so a mis-slice shows."""
        total = self.book["core"] + self.book["project"] + self.book["life"]
        rows = [[float(i)] for i in range(total)]
        return ms._select_sections(rows, include_project, include_life)

    def test_every_selection_matches_its_texts_in_length(self):
        for project in (True, False):
            for life in (True, False):
                texts = ms.anchor_texts(project, life)
                rows = self._labelled(project, life)
                self.assertEqual(len(rows), len(texts),
                                 f"project={project} life={life}")

    def test_dropping_project_but_keeping_life_is_not_a_prefix(self):
        """The case a length-based slice gets wrong without ever raising."""
        rows = self._labelled(include_project=False, include_life=True)
        core = self.book["core"]
        project = self.book["project"]
        self.assertEqual([int(r[0]) for r in rows[:core]], list(range(core)))
        self.assertEqual(int(rows[core][0]), core + project,
                         "life must start after project, not inside it")

    def test_core_only_is_the_first_core_rows(self):
        rows = self._labelled(include_project=False, include_life=False)
        self.assertEqual([int(r[0]) for r in rows],
                         list(range(self.book["core"])))


class TruncationTests(unittest.TestCase):
    def test_a_path_that_fills_the_window_is_flagged(self):
        self.assertTrue(ms.looks_truncated([[0.0]] * ms.CONTEXT_TOKENS))

    def test_a_path_that_fits_is_not_flagged(self):
        self.assertFalse(ms.looks_truncated([[0.0]] * (ms.CONTEXT_TOKENS - 1)))

    def test_an_absent_path_is_not_a_truncated_one(self):
        self.assertFalse(ms.looks_truncated(None))
        self.assertFalse(ms.looks_truncated([]))


class DiagnoseTests(unittest.TestCase):
    """The two servers fail differently and must be reported differently."""

    def setUp(self):
        self.saved = (ms.configured, ms.available, ms.trajectory)

    def tearDown(self):
        ms.configured, ms.available, ms.trajectory = self.saved

    def _embedding_server(self, alive, installed=None):
        """Stub the pooled server's two distinct questions.

        `alive` is whether it is answering; `installed` is whether it is
        configured at all. They are separate because diagnose() reads the
        first and this class previously stubbed only the second -- so a test
        named "pooled down" was really simulating a missing model file, and
        a genuine outage went unnoticed for two releases.
        """
        from core import embedding_server
        if installed is None:
            installed = alive
        self.addCleanup(setattr, embedding_server, "is_alive",
                        embedding_server.is_alive)
        self.addCleanup(setattr, embedding_server, "available",
                        embedding_server.available)
        embedding_server.is_alive = lambda timeout=2: alive
        embedding_server.available = lambda: installed

    def test_unconfigured_says_so_and_stops(self):
        ms.configured = lambda: False
        status = ms.diagnose()
        self.assertFalse(status["ready"])
        self.assertIn("pooling", status["reason"])

    def test_unpooled_down_is_not_blamed_on_the_pooled_one(self):
        ms.configured = lambda: True
        ms.available = lambda timeout=2: False
        self._embedding_server(True)
        status = ms.diagnose()
        self.assertFalse(status["ready"])
        self.assertFalse(status["unpooled"])
        self.assertIn("unpooled server is configured", status["reason"])

    def test_pooled_down_is_reported_as_the_pooled_one(self):
        """The regression this function exists for."""
        ms.configured = lambda: True
        ms.available = lambda timeout=2: True
        self._embedding_server(False, installed=False)
        status = ms.diagnose()
        self.assertFalse(status["ready"])
        self.assertTrue(status["unpooled"])
        self.assertFalse(status["pooled"])
        self.assertIn("Both are required", status["reason"])

    def test_a_stopped_pooled_server_is_never_reported_as_ready(self):
        """Installed but not running. The state that shipped as ready:True.

        diagnose() used to ask embedding_server.available(), which is a
        configuration check -- model file present, loopback URL, feature
        enabled -- and stays True through any outage. So a killed 8082 left
        every field looking healthy: pooled True, ready True, reason None,
        while anchor_vectors() returned None and the trace came back empty.
        Confirmed against the live servers on 2026-07-30 before this was
        changed to read is_alive().
        """
        ms.configured = lambda: True
        ms.available = lambda timeout=2: True
        # The model is installed; the process is simply not running.
        self._embedding_server(False, installed=True)

        status = ms.diagnose()

        self.assertFalse(status["pooled"])
        self.assertFalse(status["ready"])
        self.assertIsNotNone(status["reason"])
        # And it must send the operator to the right repair: a stopped
        # process, not a missing download.
        self.assertIn("stopped server", status["reason"])

    def test_a_missing_pooled_model_is_not_described_as_a_stopped_server(self):
        """The other half of the same distinction."""
        ms.configured = lambda: True
        ms.available = lambda timeout=2: True
        self._embedding_server(False, installed=False)

        status = ms.diagnose()

        self.assertFalse(status["ready"])
        self.assertIn("not configured", status["reason"])
        self.assertNotIn("stopped server", status["reason"])

    def test_a_truncated_input_is_reported_even_though_it_succeeded(self):
        ms.configured = lambda: True
        ms.available = lambda timeout=2: True
        ms.trajectory = lambda text, timeout=60: [[0.1]] * ms.CONTEXT_TOKENS
        self._embedding_server(True)
        status = ms.diagnose("a very long input")
        self.assertTrue(status["ready"])
        self.assertTrue(status["truncated"])
        self.assertIn("not a trace of the input", status["reason"])

    def test_a_short_input_reports_ready_and_no_reason(self):
        ms.configured = lambda: True
        ms.available = lambda timeout=2: True
        ms.trajectory = lambda text, timeout=60: [[0.1]] * 9
        self._embedding_server(True)
        status = ms.diagnose("short")
        self.assertTrue(status["ready"])
        self.assertFalse(status["truncated"])
        self.assertIsNone(status["reason"])
        self.assertEqual(status["tokens"], 9)


class UnpooledProbeTests(unittest.TestCase):
    """available() must fail the way a real request would.

    llama.cpp serves /health without authentication. A probe that reads only
    that route is satisfied by anything holding the port, which is how a
    stale service on 8084 was reported as a working embedder for an hour on
    2026-07-29 while every trajectory() call returned None.
    """

    def setUp(self):
        self.saved = (ms.requests.get, ms.MACHINESPIRIT_URL,
                      ms.MACHINESPIRIT_KEY)
        ms.MACHINESPIRIT_URL = "http://127.0.0.1:8084"
        ms.MACHINESPIRIT_KEY = "machinespirit"

    def tearDown(self):
        (ms.requests.get, ms.MACHINESPIRIT_URL,
         ms.MACHINESPIRIT_KEY) = self.saved

    def _serve(self, routes):
        """Answer per route. Records what was asked, and with which headers."""
        asked = []

        class _Response:
            def __init__(self, status, body):
                self.status_code = status
                self._body = body

            def json(self):
                if self._body is None:
                    raise ValueError("not json")
                return self._body

        def fake_get(url, headers=None, timeout=None):
            asked.append((url, dict(headers or {})))
            for suffix, answer in routes.items():
                if url.endswith(suffix):
                    return _Response(*answer)
            return _Response(404, None)

        ms.requests.get = fake_get
        return asked

    def test_a_server_that_only_answers_health_is_not_available(self):
        """The 2026-07-29 squatter, as a test."""
        asked = self._serve({
            "/health": (200, {"status": "ok"}),
            "/v1/models": (401, None),
        })

        self.assertFalse(ms.available())
        # And it must have asked the route that can actually refuse it.
        self.assertTrue(any("/v1/models" in url for url, _ in asked))

    def test_a_model_serving_endpoint_is_available(self):
        self._serve({"/v1/models": (200, {"data": [{"id": "machinespirit"}]})})
        self.assertTrue(ms.available())

    def test_a_200_carrying_no_model_is_not_available(self):
        """Up, but serving nothing. It cannot answer a trajectory either."""
        self._serve({"/v1/models": (200, {"data": []})})
        self.assertFalse(ms.available())

    def test_a_200_that_is_not_json_is_not_available(self):
        self._serve({"/v1/models": (200, None)})
        self.assertFalse(ms.available())

    def test_the_probe_presents_the_key(self):
        """A probe that skips the key is not testing the same door."""
        asked = self._serve({
            "/v1/models": (200, {"data": [{"id": "machinespirit"}]}),
        })

        ms.available()

        models = [headers for url, headers in asked if "/v1/models" in url]
        self.assertTrue(models)
        self.assertEqual(
            models[0].get("Authorization"), "Bearer machinespirit"
        )

    def test_an_unconfigured_endpoint_is_never_probed(self):
        asked = self._serve({"/v1/models": (200, {"data": [{"id": "x"}]})})
        ms.MACHINESPIRIT_URL = ""

        self.assertFalse(ms.available())
        self.assertEqual(asked, [])


class PeaksTests(unittest.TestCase):
    """Ordering is by summed support; the reported position is still the peak."""

    def test_a_concept_backed_across_the_sentence_outranks_one_lucky_spike(self):
        """The measured 77 -> 90 change, in miniature.

        'broad' never wins a position outright but is supported everywhere;
        'spike' wins once and is absent otherwise. Ranking by best position
        puts spike first, which is what cost 13 points on labelled data.
        """
        rows = [
            (0, [(0.30, "broad")]),
            (1, [(0.31, "broad")]),
            (2, [(0.29, "broad")]),
            (3, [(0.45, "spike")]),
        ]
        ordered = ms.peaks(rows)
        self.assertEqual(ordered[0][0], "broad")

    def test_the_reported_position_is_still_where_the_concept_peaked(self):
        rows = [
            (0, [(0.10, "broad")]),
            (7, [(0.40, "broad")]),
            (9, [(0.20, "broad")]),
        ]
        anchor, score, index = ms.peaks(rows)[0]
        self.assertEqual(anchor, "broad")
        self.assertAlmostEqual(score, 0.40)
        self.assertEqual(index, 7, "summing must not blur where it happened")

    def test_a_single_strong_concept_still_ranks_first_when_alone(self):
        rows = [(0, [(0.10, "weak")]), (1, [(0.90, "strong")])]
        self.assertEqual(ms.peaks(rows)[0][0], "strong")

    def test_an_empty_trace_peaks_to_nothing(self):
        self.assertEqual(ms.peaks([]), [])
        self.assertEqual(ms.peaks(None), [])


class ProfileTests(unittest.TestCase):
    """Centering has to change order, or it is not doing anything."""

    def test_centering_can_reorder_where_standardising_could_not(self):
        vectors = [[1.0, 0.0], [0.9, 0.4], [0.8, 0.6]]
        texts = ["a", "b", "c"]
        target = [0.85, 0.5]
        hits = ms.profile(target, vectors, texts, top=3)
        self.assertEqual(len(hits), 3)
        self.assertEqual({name for _, name in hits}, set(texts))

    def test_no_vectors_profiles_to_nothing_rather_than_zero(self):
        self.assertEqual(ms.profile([1.0], [], [], top=3), [])


class TrailTests(unittest.TestCase):
    """The trail must reproduce peaks() exactly, at a size that does not grow.

    Two measurements from the notes make this possible, and one of them is
    a trap. Collapsing a token to its winning anchor costs nothing
    measurable (90%/0.933 against 90%/0.920). But ranking by a single best
    position rather than by summed support was measured at 77% against
    90%, so a trail that stored only maxima would be the version that lost
    thirteen points. The support test is the one guarding that.
    """

    ANCHORS = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0]]
    TEXTS = ["first anchor", "second anchor", "third anchor"]

    def setUp(self):
        self._vectors = ms.anchor_vectors
        self._texts = ms.anchor_texts
        ms.anchor_vectors = lambda *a, **k: [row[:] for row in self.ANCHORS]
        ms.anchor_texts = lambda *a, **k: list(self.TEXTS)

    def tearDown(self):
        ms.anchor_vectors = self._vectors
        ms.anchor_texts = self._texts

    def _path(self, length):
        """A path that leans on anchor 0 with occasional excursions."""
        path = []
        for index in range(length):
            if index % 5 == 1:
                path.append([0.1, 1.0, 0.2])
            elif index % 7 == 3:
                path.append([0.2, 0.1, 1.0])
            else:
                path.append([1.0, 0.2, 0.1])
        return path

    def test_a_trail_reproduces_peaks_exactly(self):
        """The whole claim, asserted rather than described."""
        for length in (4, 9, 30, 120):
            with self.subTest(tokens=length):
                path = self._path(length)
                rows = ms.trail("", path=path)
                # The full trace, built the way trace() builds it, so the
                # comparison is against the real readout and not a stub.
                traced = [
                    (index, ms.profile(token, self.ANCHORS, self.TEXTS, 1))
                    for index, token in enumerate(path)
                ]
                self.assertEqual(ms.trail_peaks(rows), ms.peaks(traced))

    def test_the_trail_is_bounded_by_anchors_not_by_tokens(self):
        short = ms.trail("", path=self._path(8))
        long = ms.trail("", path=self._path(400))
        self.assertLessEqual(len(long), len(self.ANCHORS))
        self.assertLessEqual(len(short), len(self.ANCHORS))
        # Fifty times the tokens must not mean fifty times the storage.
        self.assertLessEqual(len(long), len(short) + 1)

    def test_support_is_summed_and_not_merely_the_peak(self):
        """Storing only maxima is the 77% version. This guards against it."""
        rows = ms.trail("", path=self._path(30))
        winner = rows[0]
        self.assertGreater(winner["hits"], 1)
        self.assertGreater(winner["support"], winner["peak"],
                           "support must accumulate across winning tokens")

    def test_the_reported_position_is_the_strongest_one(self):
        path = [[1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [1.0, 0.0, 0.0]]
        rows = ms.trail("", path=path)
        row = next(r for r in rows if r["anchor"] == "first anchor")
        self.assertIn(row["at"], (0, 1, 2))
        self.assertEqual(row["hits"], 3)

    def test_an_anchor_that_never_wins_records_nothing(self):
        rows = ms.trail("", path=[[1.0, 0.0, 0.0]] * 6)
        self.assertEqual(len(rows), 1)

    def test_it_reports_unavailable_rather_than_an_empty_trail(self):
        self.assertIsNone(ms.trail("anything", path=[]))

    def test_the_saving_is_reported_as_a_number(self):
        rows = ms.trail("", path=self._path(40))
        cost = ms.trail_cost(rows, 40, 384)
        self.assertEqual(cost["trail_values"], len(rows) * 3)
        self.assertEqual(cost["trajectory_values"], 40 * 384)
        self.assertGreater(cost["ratio"], 100)


class DensityMatrixTests(unittest.TestCase):
    """The second moment, and the claim it must never be allowed to make.

    Pooling keeps the first moment and drops the spread; rho keeps the
    spread. The danger is not that the numbers are wrong, it is that
    "covered a lot of ground" reads like "went somewhere in order" -- and
    rho is a sum over tokens, so it cannot mean that. The permutation test
    is the one that keeps the docstring honest.
    """

    def test_a_pure_state_reads_as_one_direction(self):
        matrix = ms.gram([[1.0, 0.0, 0.0]] * 5)
        self.assertAlmostEqual(ms.purity(matrix), 1.0, places=9)
        self.assertAlmostEqual(ms.effective_rank(matrix), 1.0, places=9)
        self.assertAlmostEqual(ms.von_neumann_entropy(matrix), 0.0, places=9)

    def test_orthogonal_tokens_read_as_maximally_mixed(self):
        matrix = ms.gram([[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
                          [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]])
        self.assertAlmostEqual(ms.purity(matrix), 0.25, places=9)
        self.assertAlmostEqual(ms.effective_rank(matrix), 4.0, places=9)
        self.assertAlmostEqual(ms.von_neumann_entropy(matrix),
                               math.log(4), places=9)

    def test_the_gram_matrix_has_trace_one(self):
        matrix = ms.gram([[3.0, 1.0], [-2.0, 5.0], [0.5, 0.5]])
        self.assertAlmostEqual(sum(matrix[i][i] for i in range(3)),
                               1.0, places=9)

    def test_jacobi_matches_the_closed_form_for_two_by_two(self):
        a, b, d = 2.0, 0.7, -1.0
        root = math.sqrt((a - d) ** 2 + 4 * b * b)
        expected = sorted([((a + d) + root) / 2, ((a + d) - root) / 2],
                          reverse=True)
        for got, want in zip(ms._eigenvalues_symmetric([[a, b], [b, d]]),
                             expected):
            self.assertAlmostEqual(got, want, places=9)

    def test_it_is_permutation_invariant_as_the_docstring_says(self):
        """The load-bearing negative claim: ground covered, never order."""
        path = [[1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.5, 0.5, 0.7],
                [0.0, 0.0, 1.0], [0.9, 0.1, 0.0]]
        first = ms.spread("", path=path)
        shuffled = [path[i] for i in (3, 0, 4, 1, 2)]
        second = ms.spread("", path=shuffled)

        self.assertAlmostEqual(first["purity"], second["purity"], places=9)
        self.assertAlmostEqual(first["entropy"], second["entropy"], places=7)

    def test_breadth_moves_it_and_length_alone_does_not(self):
        """Measured on live traces: one topic saturates, topics do not.

        A long single-topic passage must not read as broad simply for
        being long, or the observable is a token counter with a Greek
        letter on it.
        """
        narrow = [[1.0, 0.0, 0.0]] * 40
        narrow_short = [[1.0, 0.0, 0.0]] * 8
        broad = [[1.0, 0.0, 0.0]] * 20 + [[0.0, 1.0, 0.0]] * 20

        self.assertAlmostEqual(ms.effective_rank(ms.gram(narrow)),
                               ms.effective_rank(ms.gram(narrow_short)),
                               places=6)
        self.assertGreater(ms.effective_rank(ms.gram(broad)),
                           ms.effective_rank(ms.gram(narrow)) + 0.5)

    def test_an_unavailable_server_reports_nothing_rather_than_zero(self):
        """Zero spread is a reading. Absent is not, and must not look like one."""
        self.assertIsNone(ms.spread("anything", path=[]))

    def test_a_truncated_trajectory_says_so_in_its_own_result(self):
        path = [[1.0, 0.0]] * ms.CONTEXT_TOKENS
        self.assertTrue(ms.spread("", path=path)["truncated"])


if __name__ == "__main__":
    unittest.main()

