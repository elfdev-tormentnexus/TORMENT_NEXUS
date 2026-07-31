"""Regression tests for the scoped embedding backfill.

These cover the behaviours the live run exposed and the review demanded:
a poison chunk must not stall the backlog, an ambiguous failure must never be
recorded as a permanent verdict, the ceiling must not overshoot, and a partial
or mismatched vector population must not tilt ordinary retrieval.
"""

import os
import sqlite3
import tempfile
import threading
import time
import unittest
from unittest import mock

from knowledge import library


class ScopedBackfillTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        root = self.folder.name
        self.builtin = os.path.join(root, "builtin")
        self.user = os.path.join(root, "user")
        os.makedirs(self.builtin)
        os.makedirs(self.user)
        self.library = library.KnowledgeLibrary(
            builtin_dir=self.builtin,
            user_dir=self.user,
            database_path=os.path.join(root, "library.sqlite3"),
        )
        self.library.set_embedding_enabled(True)

    def _write(self, folder, name, body):
        with open(os.path.join(folder, name), "w", encoding="utf-8") as handle:
            handle.write(body)

    def _seed(self, chunks=6):
        body = "\n\n".join(
            f"# Head {n}\n\nBody number {n} carries enough distinct words here."
            for n in range(chunks)
        )
        self._write(self.builtin, "cards.md", body)
        self.library.rebuild()

    def test_backoff_grows_and_is_capped(self):
        self.assertGreater(library._retry_delay(2), library._retry_delay(1))
        self.assertLessEqual(
            library._retry_delay(50), library.EMBED_RETRY_MAX_SECONDS
        )

    def test_fresh_database_defaults_off_and_normal_worker_does_not_embed(self):
        fresh_database = os.path.join(self.folder.name, "fresh.sqlite3")
        fresh = library.KnowledgeLibrary(
            builtin_dir=self.builtin,
            user_dir=self.user,
            database_path=fresh_database,
        )
        self._write(
            self.builtin,
            "fresh.md",
            "# Fresh reference\n\nA fresh install has pending reference text.",
        )
        self.assertFalse(fresh.embedding_enabled())

        original = library._library
        library.reset_for_tests(fresh)
        self.addCleanup(library.reset_for_tests, original)
        with (
            mock.patch.object(library.embedding_server, "available", return_value=True),
            mock.patch.object(library.embedding_server, "is_alive", return_value=True),
            mock.patch.object(library.embedding_server, "embed") as embed,
        ):
            library.start_worker()
            deadline = time.time() + 2
            while fresh.status()["chunks"] < 1 and time.time() < deadline:
                time.sleep(0.01)
            time.sleep(0.08)
        self.assertGreaterEqual(fresh.status()["chunks"], 1)
        embed.assert_not_called()
        state = fresh.status()["embedding"]
        self.assertFalse(state["enabled"])
        self.assertGreater(state["pending"], 0)
        self.assertEqual(state["stall_reason"], "disabled")

    def test_enable_and_disable_choices_survive_reopen(self):
        self.assertTrue(self.library.embedding_enabled())
        reopened = library.KnowledgeLibrary(
            builtin_dir=self.builtin,
            user_dir=self.user,
            database_path=self.library.database_path,
        )
        self.assertTrue(reopened.embedding_enabled())
        reopened.set_embedding_enabled(False)
        reopened_again = library.KnowledgeLibrary(
            builtin_dir=self.builtin,
            user_dir=self.user,
            database_path=self.library.database_path,
        )
        self.assertFalse(reopened_again.embedding_enabled())

    def test_disable_prevents_new_batches_and_direct_work(self):
        self._seed(chunks=3)
        calls = []

        def disable_after_first_batch(texts, timeout=None):
            del timeout
            calls.append(list(texts))
            self.library.set_embedding_enabled(False)
            return [[1.0, 0.0] for _ in texts]

        with (
            mock.patch.object(library, "EMBED_BATCH_SIZE", 1),
            mock.patch.object(library.embedding_server, "available", return_value=True),
            mock.patch.object(library.embedding_server, "is_alive", return_value=True),
            mock.patch.object(library.embedding_server, "model_identity", return_value="m"),
            mock.patch.object(
                library.embedding_server,
                "embed",
                side_effect=disable_after_first_batch,
            ),
        ):
            self.assertEqual(self.library.embed_missing(max_batches=3), 1)
            self.assertEqual(self.library.embed_missing(max_batches=3), 0)
        self.assertEqual(len(calls), 1)

    def test_one_pass_charges_a_row_at_most_one_attempt(self):
        """The defect: three failures in one call are one outage, not three."""
        self._seed(chunks=3)

        def always_fail(texts, timeout=None):
            return None

        with (
            mock.patch.object(library.embedding_server, "embed", always_fail),
            mock.patch.object(
                library.embedding_server, "available", return_value=True
            ),
            mock.patch.object(
                library.embedding_server, "is_alive", return_value=True
            ),
            mock.patch.object(
                library.embedding_server, "model_identity", return_value="m"
            ),
            mock.patch.object(
                self.library, "_embedder_healthy", return_value=True
            ),
        ):
            # Many batches inside ONE scheduled pass.
            self.library.embed_missing(max_batches=10)

        with self.library._connect() as connection:
            rows = list(connection.execute(
                "SELECT attempts FROM embed_attempts"
            ))
        self.assertTrue(rows, "no attempt was recorded at all")
        for row in rows:
            self.assertEqual(
                row["attempts"], 1,
                "a single pass charged more than one attempt",
            )

    def test_quarantine_is_visible_and_resettable(self):
        self._seed(chunks=2)
        identity = self.library._vector_identity()
        with self.library._connect(write=True) as connection:
            chunk = next(iter(connection.execute(
                "SELECT id, content_hash FROM chunks ORDER BY id"
            )))
            connection.execute(
                """
                INSERT INTO embed_attempts
                    (chunk_id, vector_identity, content_hash,
                     attempts, last_pass,
                     next_retry_utc, last_error)
                VALUES (?, ?, ?, ?, 'p', 0, 'too long')
                """,
                (
                    chunk["id"], identity, chunk["content_hash"],
                    library.EMBED_MAX_ATTEMPTS,
                ),
            )
            # A non-terminal row is backoff telemetry, not quarantine, and
            # must survive a bulk quarantine reset.
            other = list(connection.execute(
                "SELECT id, content_hash FROM chunks ORDER BY id"
            ))[1]
            connection.execute(
                """
                INSERT INTO embed_attempts
                    (chunk_id, vector_identity, content_hash,
                     attempts, last_pass, next_retry_utc, last_error)
                VALUES (?, ?, ?, 1, 'q', 9999999999, 'retry later')
                """,
                (other["id"], identity, other["content_hash"]),
            )
            connection.commit()

        report = self.library.embed_quarantine()
        self.assertEqual(report["quarantined"], 1)
        self.assertEqual(report["rows"][0]["chunk_id"], chunk["id"])
        self.assertEqual(report["rows"][0]["last_error"], "too long")

        self.assertEqual(self.library.clear_embed_quarantine(), 1)
        self.assertEqual(self.library.embed_quarantine()["quarantined"], 0)
        with self.library._connect() as connection:
            remaining = list(connection.execute(
                "SELECT attempts FROM embed_attempts"
            ))
        self.assertEqual([row["attempts"] for row in remaining], [1])

    def test_bounded_text_cuts_on_a_character_boundary(self):
        text = "é" * (library.EMBED_TEXT_BYTE_LIMIT * 2)
        bounded = library._bounded_embed_text(text)
        encoded = bounded.encode("utf-8")
        self.assertLessEqual(len(encoded), library.EMBED_TEXT_BYTE_LIMIT)
        # Decoding must not have produced a partial character.
        self.assertEqual(bounded, encoded.decode("utf-8"))

    def test_truncation_policy_is_part_of_the_vector_identity(self):
        with mock.patch.object(
            library.embedding_server, "model_identity", return_value="m"
        ):
            self.assertIn(
                library.EMBED_TRUNCATION_POLICY,
                self.library._vector_identity(),
            )

    def test_a_transient_server_failure_never_records_an_attempt(self):
        """The defect the review caught: ambiguity must not become a verdict."""
        self._seed()
        ident = self.library._vector_identity()
        rows = [
            {"id": 1, "source_id": 1, "content_hash": "h", "vector_model": ""}
        ]
        with (
            mock.patch.object(
                library.embedding_server, "embed", return_value=None
            ),
            mock.patch.object(
                self.library, "_embedder_healthy", return_value=False
            ),
            mock.patch.object(self.library, "_commit_embedded") as commit,
        ):
            self.library._embed_rows_individually(rows, ["text"], ident)
        # Nothing retired; the untouched batch is simply committed as-is.
        commit.assert_called_once()
        self.assertEqual(commit.call_args[0][0], [])

    def test_scoped_ceiling_stays_under_the_exact_scan_limit(self):
        """Embedding past the scan limit would disable semantic search."""
        self.assertLess(
            library.EMBED_GLOBAL_CEILING, library.MAX_EXPLICIT_VECTOR_SCAN
        )

    def test_good_poison_good_lifecycle_through_the_real_database(self):
        """The whole path: a poison row must not block the rows behind it.

        Exercises embed_missing() against the actual SQL rather than checking
        marker arithmetic: one chunk always fails, the rest must still end up
        embedded, and the failing row must carry an attempt count rather than
        a vector.
        """
        self._seed(chunks=5)
        poison = {"seen": 0}

        def fake_embed(texts, timeout=None):
            # Batch call fails whenever the poison text is present; the
            # per-row retry then succeeds for everything except the poison.
            if any("Body number 2" in t for t in texts) and len(texts) > 1:
                return None
            if len(texts) == 1 and "Body number 2" in texts[0]:
                poison["seen"] += 1
                return None
            return [[1.0, 0.0] for _ in texts]

        with (
            mock.patch.object(library.embedding_server, "embed", fake_embed),
            mock.patch.object(
                library.embedding_server, "available", return_value=True
            ),
            mock.patch.object(
                library.embedding_server, "is_alive", return_value=True
            ),
            mock.patch.object(
                library.embedding_server, "model_identity", return_value="m"
            ),
        ):
            self.library.embed_missing(max_batches=6)

            ident = self.library._vector_identity()
            with self.library._connect() as connection:
                rows = list(connection.execute(
                    "SELECT text, vector, vector_model FROM chunks ORDER BY id"
                ))

        self.assertTrue(poison["seen"] >= 1, "poison row was never isolated")
        good = [r for r in rows if "Body number 2" not in (r["text"] or "")]
        bad = [r for r in rows if "Body number 2" in (r["text"] or "")]

        # Every healthy chunk behind the poison one still got a vector.
        self.assertTrue(good, "fixture produced no healthy chunks")
        for row in good:
            self.assertIsNotNone(row["vector"])
            self.assertEqual(row["vector_model"], ident)

        # The poison chunk never gets a vector, and its failure is recorded
        # in embed_attempts rather than written over the chunk row.
        self.assertTrue(bad, "fixture produced no poison chunk")
        for row in bad:
            self.assertIsNone(row["vector"])
        with self.library._connect() as connection:
            attempts = list(connection.execute(
                "SELECT chunk_id, attempts FROM embed_attempts"
            ))
        self.assertTrue(attempts, "no attempt row was recorded")
        for row in attempts:
            self.assertGreaterEqual(row["attempts"], 1)

    def test_malformed_member_in_sized_batch_is_salvaged_and_backed_off(self):
        """A NaN member must not leave the same batch at the queue head."""
        self._seed(chunks=3)
        calls = []

        def fake_embed(texts, timeout=None):
            del timeout
            calls.append(list(texts))
            if len(texts) > 1:
                # Correct row count, but the middle vector is unusable.
                return [[1.0, 0.0], [float("nan"), 0.0], [1.0, 0.0]]
            if "Body number 1" in texts[0]:
                return [[float("nan"), 0.0]]
            return [[1.0, 0.0]]

        with (
            mock.patch.object(library.embedding_server, "available", return_value=True),
            mock.patch.object(library.embedding_server, "is_alive", return_value=True),
            mock.patch.object(library.embedding_server, "model_identity", return_value="m"),
            mock.patch.object(library.embedding_server, "embed", side_effect=fake_embed),
            mock.patch.object(self.library, "_embedder_healthy", return_value=True),
        ):
            self.library.embed_missing(max_batches=1)

        self.assertEqual(len(calls), 4, "batch was not retried row by row")
        with self.library._connect() as connection:
            rows = list(connection.execute(
                "SELECT text, vector FROM chunks ORDER BY id"
            ))
            attempts = list(connection.execute(
                "SELECT chunk_id, attempts FROM embed_attempts"
            ))
        good = [row for row in rows if "Body number 1" not in row["text"]]
        bad = [row for row in rows if "Body number 1" in row["text"]]
        self.assertTrue(all(row["vector"] is not None for row in good))
        self.assertEqual(len(bad), 1)
        self.assertIsNone(bad[0]["vector"])
        self.assertEqual([row["attempts"] for row in attempts], [1])

    def test_dimension_mismatch_in_sized_batch_is_retried_individually(self):
        """A mixed-dimension batch is not accepted or retried forever."""
        self._seed(chunks=3)
        calls = []

        def fake_embed(texts, timeout=None):
            del timeout
            calls.append(list(texts))
            if len(texts) > 1:
                return [[1.0, 0.0], [1.0, 0.0, 0.0], [1.0, 0.0]]
            return [[1.0, 0.0]]

        with (
            mock.patch.object(library.embedding_server, "available", return_value=True),
            mock.patch.object(library.embedding_server, "is_alive", return_value=True),
            mock.patch.object(library.embedding_server, "model_identity", return_value="m"),
            mock.patch.object(library.embedding_server, "embed", side_effect=fake_embed),
        ):
            self.library.embed_missing(max_batches=1)

        self.assertEqual(len(calls), 4, "batch was not retried row by row")
        with self.library._connect() as connection:
            rows = list(connection.execute(
                "SELECT vector FROM chunks ORDER BY id"
            ))
            attempts = connection.execute(
                "SELECT COUNT(*) FROM embed_attempts"
            ).fetchone()[0]
        self.assertTrue(all(row["vector"] is not None for row in rows))
        self.assertEqual(attempts, 0)

    def test_a_failure_cannot_erase_a_concurrent_success(self):
        """A stale attempt write must not blank a vector stored meanwhile."""
        self._seed(chunks=2)
        ident = self.library._vector_identity()
        with self.library._connect(write=True) as connection:
            row = next(iter(connection.execute(
                "SELECT id, source_id, content_hash FROM chunks ORDER BY id"
            )))
            # Another worker has just embedded it.
            connection.execute(
                "UPDATE chunks SET vector=?, vector_model=? WHERE id=?",
                (library._pack_vector([1.0, 0.0]), ident, row["id"]),
            )
            connection.commit()

        # This worker still holds the pre-success state it read earlier.
        stale = {
            "id": row["id"], "source_id": row["source_id"],
            "content_hash": row["content_hash"], "vector_model": "",
        }
        with (
            mock.patch.object(
                library.embedding_server, "embed", return_value=None
            ),
            mock.patch.object(
                self.library, "_embedder_healthy", return_value=True
            ),
        ):
            self.library._embed_rows_individually([stale], ["text"], ident)

        with self.library._connect() as connection:
            after = next(iter(connection.execute(
                "SELECT vector, vector_model FROM chunks WHERE id=?",
                (row["id"],),
            )))
        self.assertIsNotNone(after["vector"], "concurrent success was erased")
        self.assertEqual(after["vector_model"], ident)
        with self.library._connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM embed_attempts"
                ).fetchone()[0],
                0,
                "a stale failure contaminated a concurrently completed row",
            )

    def test_model_and_content_changes_receive_fresh_attempt_budgets(self):
        self._seed(chunks=1)
        with self.library._connect(write=True) as connection:
            row = connection.execute(
                "SELECT id, content_hash FROM chunks"
            ).fetchone()
            connection.execute(
                """
                INSERT INTO embed_attempts(
                    chunk_id, vector_identity, content_hash, attempts,
                    last_pass, next_retry_utc, last_error
                ) VALUES(?, ?, ?, ?, 'old', 9999999999, 'old failure')
                """,
                (
                    row["id"],
                    f"model-a+{library.EMBED_TRUNCATION_POLICY}",
                    row["content_hash"],
                    library.EMBED_MAX_ATTEMPTS,
                ),
            )
            connection.commit()

        calls = []

        def succeed(texts, timeout=None):
            del timeout
            calls.extend(texts)
            return [[1.0, 0.0] for _ in texts]

        with (
            mock.patch.object(library.embedding_server, "available", return_value=True),
            mock.patch.object(library.embedding_server, "is_alive", return_value=True),
            mock.patch.object(library.embedding_server, "model_identity", return_value="model-b"),
            mock.patch.object(library.embedding_server, "embed", side_effect=succeed),
        ):
            self.assertEqual(self.library.embed_missing(max_batches=1), 1)
        self.assertEqual(len(calls), 1, "model A quarantine leaked into model B")

        # Preserve the row id while changing the exact input hash.  The stale
        # model-A terminal record must not suppress this rewritten content.
        with self.library._connect(write=True) as connection:
            new_hash = "new-content-hash"
            connection.execute(
                """
                UPDATE chunks
                SET text='rewritten reference body', content_hash=?,
                    vector=NULL, vector_model=''
                WHERE id=?
                """,
                (new_hash, row["id"]),
            )
            connection.commit()

        calls.clear()
        with (
            mock.patch.object(library.embedding_server, "available", return_value=True),
            mock.patch.object(library.embedding_server, "is_alive", return_value=True),
            mock.patch.object(library.embedding_server, "model_identity", return_value="model-a"),
            mock.patch.object(library.embedding_server, "embed", side_effect=succeed),
        ):
            self.assertEqual(self.library.embed_missing(max_batches=1), 1)
        self.assertEqual(len(calls), 1, "old content quarantine leaked into new text")

    def test_three_real_failure_passes_back_off_300_600_1200_seconds(self):
        self._seed(chunks=1)
        identity = "m+" + library.EMBED_TRUNCATION_POLICY

        for attempt, now in enumerate((1000.0, 2000.0, 4000.0), 1):
            with (
                mock.patch.object(library.time, "time", return_value=now),
                mock.patch.object(library.embedding_server, "available", return_value=True),
                mock.patch.object(library.embedding_server, "is_alive", return_value=True),
                mock.patch.object(library.embedding_server, "model_identity", return_value="m"),
                mock.patch.object(library.embedding_server, "embed", return_value=None),
                mock.patch.object(self.library, "_embedder_healthy", return_value=True),
            ):
                self.assertEqual(self.library.embed_missing(max_batches=1), 0)
            with self.library._connect() as connection:
                stored = connection.execute(
                    """
                    SELECT attempts, next_retry_utc FROM embed_attempts
                    WHERE vector_identity=?
                    """,
                    (identity,),
                ).fetchone()
            self.assertEqual(stored["attempts"], attempt)
            self.assertEqual(
                stored["next_retry_utc"] - now,
                (300.0, 600.0, 1200.0)[attempt - 1],
            )

    def test_success_clears_current_attempt_history(self):
        self._seed(chunks=1)
        identity = "m+" + library.EMBED_TRUNCATION_POLICY
        with self.library._connect(write=True) as connection:
            row = connection.execute(
                "SELECT id, content_hash FROM chunks"
            ).fetchone()
            connection.execute(
                """
                INSERT INTO embed_attempts(
                    chunk_id, vector_identity, content_hash, attempts,
                    last_pass, next_retry_utc, last_error
                ) VALUES(?, ?, ?, 2, 'old', 0, 'old failure')
                """,
                (row["id"], identity, row["content_hash"]),
            )
            connection.commit()

        with (
            mock.patch.object(library.embedding_server, "available", return_value=True),
            mock.patch.object(library.embedding_server, "is_alive", return_value=True),
            mock.patch.object(library.embedding_server, "model_identity", return_value="m"),
            mock.patch.object(library.embedding_server, "embed", return_value=[[1.0, 0.0]]),
        ):
            self.assertEqual(self.library.embed_missing(max_batches=1), 1)

        with self.library._connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM embed_attempts"
                ).fetchone()[0],
                0,
            )

    def test_stale_failure_cannot_attach_to_replaced_content(self):
        self._seed(chunks=1)
        identity = self.library._vector_identity()
        with self.library._connect(write=True) as connection:
            row = connection.execute(
                "SELECT id, source_id, content_hash FROM chunks"
            ).fetchone()
            connection.execute(
                "UPDATE chunks SET content_hash='replacement' WHERE id=?",
                (row["id"],),
            )
            connection.commit()

        stale = dict(row)
        stale["attempts"] = 0
        with (
            mock.patch.object(library.embedding_server, "embed", return_value=None),
            mock.patch.object(self.library, "_embedder_healthy", return_value=True),
        ):
            self.library._embed_rows_individually(
                [stale], ["old text"], identity, "stale-pass"
            )
        with self.library._connect() as connection:
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM embed_attempts"
                ).fetchone()[0],
                0,
            )

    def test_database_lease_excludes_a_second_library_instance(self):
        self._seed(chunks=2)
        other = library.KnowledgeLibrary(
            builtin_dir=self.builtin,
            user_dir=self.user,
            database_path=self.library.database_path,
        )
        entered = threading.Event()
        release = threading.Event()
        calls = []

        def blocked_embed(texts, timeout=None):
            del timeout
            calls.append(list(texts))
            entered.set()
            self.assertTrue(release.wait(3), "test did not release embedder")
            return [[1.0, 0.0] for _ in texts]

        with (
            mock.patch.object(library.embedding_server, "available", return_value=True),
            mock.patch.object(library.embedding_server, "is_alive", return_value=True),
            mock.patch.object(library.embedding_server, "model_identity", return_value="m"),
            mock.patch.object(library.embedding_server, "embed", side_effect=blocked_embed),
        ):
            worker = threading.Thread(
                target=self.library.embed_missing, kwargs={"max_batches": 1}
            )
            worker.start()
            self.assertTrue(entered.wait(3), "first pass never reached embedder")
            try:
                self.assertEqual(other.embed_missing(max_batches=1), 0)
            finally:
                release.set()
                worker.join(3)
        self.assertFalse(worker.is_alive())
        self.assertEqual(len(calls), 1, "concurrent pass crossed the database lease")

    def test_fair_target_and_migration_exclude_old_out_of_target_vectors(self):
        self._write(
            self.builtin,
            "cards.md",
            "# Card one\n\nFirst built in body.\n\n# Card two\n\nSecond built in body.",
        )
        for source in range(3):
            self._write(
                self.user,
                f"source-{source}.md",
                "\n\n".join(
                    f"# User {source} round {round_}\n\n"
                    f"User source {source} body round {round_} has enough words."
                    for round_ in range(3)
                ),
            )
        self.library.rebuild()
        identity = "m+" + library.EMBED_TRUNCATION_POLICY
        with self.library._connect(write=True) as connection:
            connection.execute(
                "UPDATE chunks SET vector=?, vector_model=?",
                (library._pack_vector([1.0, 0.0]), identity),
            )
            connection.commit()

        with (
            mock.patch.object(library, "EMBED_GLOBAL_CEILING", 5),
            mock.patch.object(library, "EMBED_SOURCE_CAP", 3),
            mock.patch.object(library.embedding_server, "model_identity", return_value="m"),
            mock.patch.object(library.embedding_server, "available", return_value=True),
        ):
            state = self.library._embedding_state(identity)
            with self.library._connect() as connection:
                target = connection.execute(
                    library._EMBED_TARGET_CTE + """
                    SELECT scope, source_id, source_round FROM embed_target
                    ORDER BY
                        CASE WHEN scope='built-in' THEN 0 ELSE 1 END,
                        CASE WHEN scope='built-in' THEN 0 ELSE source_round END,
                        CASE WHEN scope='built-in' THEN path ELSE sha256 END,
                        path, ordinal, content_hash, id
                    """,
                    self.library._target_parameters(identity),
                ).fetchall()
            self.assertEqual(state["target"], 5)
            self.assertGreater(state["out_of_target"], 0)
            self.assertEqual([row["scope"] for row in target[:2]], ["built-in"] * 2)
            user_target = target[2:]
            self.assertEqual(len({row["source_id"] for row in user_target}), 3)
            self.assertEqual([row["source_round"] for row in user_target], [1, 1, 1])
            self.assertEqual(len(self.library._semantic([1.0, 0.0], 20)), 5)

        with (
            mock.patch.object(library, "EMBED_GLOBAL_CEILING", 5),
            mock.patch.object(library, "EMBED_SOURCE_CAP", 3),
            mock.patch.object(library.embedding_server, "model_identity", return_value="m"),
            mock.patch.object(library.embedding_server, "available", return_value=True),
            mock.patch.object(library.embedding_server, "is_alive", return_value=True),
        ):
            self.library.embed_missing(max_batches=0)
        with self.library._connect() as connection:
            current_count = connection.execute(
                "SELECT COUNT(*) FROM chunks WHERE vector_model=?",
                (identity,),
            ).fetchone()[0]
        self.assertEqual(current_count, 5)

    def test_status_exposes_due_backoff_quarantine_and_coverage(self):
        self._seed(chunks=3)
        identity = "m+" + library.EMBED_TRUNCATION_POLICY
        with self.library._connect(write=True) as connection:
            rows = list(connection.execute(
                "SELECT id, content_hash FROM chunks ORDER BY id"
            ))
            connection.execute(
                "UPDATE chunks SET vector=?, vector_model=? WHERE id=?",
                (library._pack_vector([1.0, 0.0]), identity, rows[0]["id"]),
            )
            connection.execute(
                """
                INSERT INTO embed_attempts VALUES(?, ?, ?, 1, 'p', ?, 'later')
                """,
                (rows[1]["id"], identity, rows[1]["content_hash"], time.time() + 600),
            )
            connection.execute(
                """
                INSERT INTO embed_attempts VALUES(?, ?, ?, ?, 'q', 0, 'poison')
                """,
                (
                    rows[2]["id"], identity, rows[2]["content_hash"],
                    library.EMBED_MAX_ATTEMPTS,
                ),
            )
            connection.commit()

        with (
            mock.patch.object(library.embedding_server, "model_identity", return_value="m"),
            mock.patch.object(library.embedding_server, "available", return_value=True),
        ):
            state = self.library.status()
        embedding = state["embedding"]
        self.assertEqual(embedding["eligible"], 3)
        self.assertEqual(embedding["target"], 2)
        self.assertEqual(embedding["embedded"], 1)
        self.assertEqual(embedding["pending"], 1)
        self.assertEqual(embedding["due"], 0)
        self.assertEqual(embedding["backoff"], 1)
        self.assertEqual(embedding["quarantined"], 1)
        self.assertEqual(embedding["coverage"], 0.5)
        self.assertFalse(embedding["complete"])
        self.assertEqual(embedding["stall_reason"], "waiting-for-retry")

    def test_worker_quiesces_when_target_has_no_due_rows(self):
        class BackoffLibrary:
            def __init__(self):
                self.rebuild_calls = 0
                self.embed_calls = 0
                self._last_error = ""

            def rebuild(self):
                self.rebuild_calls += 1
                return {"changed": 0, "removed": 0, "errors": []}

            @staticmethod
            def reclassify_pending(max_sources=None):
                del max_sources
                return {"updated": 0, "remaining": 0}

            def embed_missing(self, max_batches=4):
                del max_batches
                self.embed_calls += 1
                return 0

            @staticmethod
            def status():
                return {
                    "chunks": 100,
                    "embedded": 0,
                    "embedding_due": 0,
                    "embedding": {"next_retry_utc": 0.0},
                }

        original = library._library
        fake = BackoffLibrary()
        library.reset_for_tests(fake)
        self.addCleanup(library.reset_for_tests, original)
        with (
            mock.patch.object(library, "WORKER_RETRY_SECONDS", 0.02),
            mock.patch.object(library.embedding_server, "available", return_value=True),
        ):
            library.start_worker()
            deadline = time.time() + 2
            while fake.embed_calls < 1 and time.time() < deadline:
                time.sleep(0.01)
            self.assertEqual(fake.embed_calls, 1)
            time.sleep(0.12)
            self.assertEqual(fake.embed_calls, 1)

    def test_schema_two_attempts_migrate_to_fresh_identity_scoped_rows(self):
        self._seed(chunks=1)
        self.library._schema_ready = False
        connection = sqlite3.connect(self.library.database_path)
        try:
            connection.execute("PRAGMA foreign_keys=OFF")
            connection.execute("DROP TABLE embed_attempts")
            connection.execute(
                """
                CREATE TABLE embed_attempts(
                    chunk_id INTEGER PRIMARY KEY,
                    content_hash TEXT NOT NULL DEFAULT '',
                    attempts INTEGER NOT NULL DEFAULT 0,
                    last_pass TEXT NOT NULL DEFAULT '',
                    next_retry_utc REAL NOT NULL DEFAULT 0.0,
                    last_error TEXT NOT NULL DEFAULT ''
                )
                """
            )
            chunk = connection.execute(
                "SELECT id, content_hash FROM chunks"
            ).fetchone()
            connection.execute(
                "INSERT INTO embed_attempts VALUES(?, ?, 3, 'p', 0, 'legacy')",
                chunk,
            )
            connection.execute(
                "UPDATE library_meta SET value='2' WHERE key='schema_version'"
            )
            connection.commit()
        finally:
            connection.close()

        reopened = library.KnowledgeLibrary(
            builtin_dir=self.builtin,
            user_dir=self.user,
            database_path=self.library.database_path,
        )
        with reopened._connect() as connection:
            columns = {
                row["name"] for row in connection.execute(
                    "PRAGMA table_info(embed_attempts)"
                )
            }
            count = connection.execute(
                "SELECT COUNT(*) FROM embed_attempts"
            ).fetchone()[0]
        self.assertIn("vector_identity", columns)
        self.assertEqual(count, 0)

    def test_cosine_bonus_is_all_or_none_across_the_candidate_set(self):
        self._seed()
        ident = self.library._vector_identity()
        with self.library._connect(write=True) as connection:
            ids = [
                row["id"]
                for row in connection.execute("SELECT id FROM chunks ORDER BY id")
            ]
            self.assertGreaterEqual(len(ids), 2)
            # Only the first chunk gets a vector: a partial population.
            connection.execute(
                "UPDATE chunks SET vector=?, vector_model=? WHERE id=?",
                (library._pack_vector([1.0, 0.0]), ident, ids[0]),
            )
            connection.commit()

        results = self.library.search("body", query_vector=[1.0, 0.0], limit=5)
        # With the set incomparable, nothing may be scored as semantic.
        for row in results:
            self.assertNotEqual(dict(row).get("retrieval"), "hybrid")
            self.assertIsNone(dict(row).get("similarity"))

    def test_out_of_target_vectors_cannot_rerank_lexical_candidates(self):
        self._seed(chunks=3)
        identity = "m+" + library.EMBED_TRUNCATION_POLICY
        with self.library._connect(write=True) as connection:
            connection.execute(
                "UPDATE chunks SET vector=?, vector_model=?",
                (library._pack_vector([1.0, 0.0]), identity),
            )
            connection.commit()

        with (
            mock.patch.object(library, "EMBED_GLOBAL_CEILING", 1),
            mock.patch.object(library.embedding_server, "model_identity", return_value="m"),
        ):
            results = self.library.search(
                "body", query_vector=[1.0, 0.0], limit=5
            )
        self.assertGreaterEqual(len(results), 2)
        for row in results:
            self.assertEqual(row["retrieval"], "lexical")
            self.assertIsNone(row["similarity"])


if __name__ == "__main__":
    unittest.main()
