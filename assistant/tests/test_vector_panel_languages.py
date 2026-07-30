"""The panel shows the two languages, and cannot contradict either one.

A panel that renders beautifully and disagrees with the instrument it claims
to show is worse than no panel. These hold the two agreements: machinespirit
above must be what `trace` prints, and machinesoul below must be the bytes a
capsule actually stores.
"""

import re
import importlib.util
import os
import unittest
from unittest import mock

import main as assistant_main
from core import machinespirit
from core import calibration
from ui import vector_panel


ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
_spec = importlib.util.spec_from_file_location(
    "_machinesoul_for_panel_test", os.path.join(ROOT, "tools", "machinesoul.py")
)
_machinesoul = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_machinesoul)


# The shape read_path() returns: (token index, [(support, anchor text), ...]).
READINGS = [
    (0, [(0.46, "grandparents telling the same story again")]),
    (1, [(0.42, "a promise made to a dying person"),
         (0.20, "grandparents telling the same story again")]),
    (2, [(0.51, "grandparents telling the same story again")]),
]


class TraceAgreementTests(unittest.TestCase):
    def test_trace_delegates_to_the_function_the_panel_is_fed(self):
        # If trace() ever stops going through read_path(), the panel and the
        # printed readout become two implementations that can drift.
        with mock.patch.object(machinespirit, "trajectory",
                               return_value=[[0.1, 0.2]]), \
             mock.patch.object(machinespirit, "read_path",
                               return_value=READINGS) as read:
            result = machinespirit.trace("some text", top=3)

        read.assert_called_once()
        self.assertEqual(result, READINGS)

    def test_read_path_refuses_an_empty_path_rather_than_inventing_one(self):
        self.assertIsNone(machinespirit.read_path(None))
        self.assertIsNone(machinespirit.read_path([]))

    def test_panel_takes_the_readout_without_re_ranking_it(self):
        field = vector_panel.Field()
        field.set_spirit(READINGS)

        # One lane per distinct anchor, in first-seen order, and every token
        # keeps every anchor the readout gave it.
        self.assertEqual(len(field.spirit), len(READINGS))
        self.assertEqual(len(field.spirit_labels), 2)
        self.assertEqual(field.spirit_labels[0],
                         "grandparents telling the same story again")
        self.assertEqual([len(row) for row in field.spirit], [1, 2, 1])

    def test_one_concept_holds_one_lane_across_the_whole_readout(self):
        # This is what makes the panel legible: watching a row light up
        # across columns is watching a concept persist through a sentence.
        field = vector_panel.Field()
        field.set_spirit(READINGS)

        first = field.spirit[0][0][0]
        last = field.spirit[2][0][0]
        self.assertEqual(first, last)

    def test_support_survives_into_the_panel_unchanged(self):
        field = vector_panel.Field()
        field.set_spirit(READINGS)

        supports = [support for row in field.spirit for _, support in row]
        self.assertEqual(sorted(supports), sorted([0.46, 0.42, 0.20, 0.51]))


class MachinesoulFieldTests(unittest.TestCase):
    def test_hazard_wiring_uses_the_payload_from_the_real_capsule(self):
        capsule = os.path.join(
            ROOT, "assistant", "core", "SABLE_CALIBRATION1.png"
        )
        payload, _meta = _machinesoul.extract(capsule)
        with open(calibration.RECORD_FILE, "rb") as source:
            self.assertEqual(payload, source.read())

        old = assistant_main._hazard_soul_payload
        assistant_main._hazard_soul_payload = None
        try:
            with mock.patch.object(
                assistant_main.command_handlers,
                "is_experimental_mode",
                return_value=True,
            ), mock.patch.object(
                assistant_main.ui, "panel_active", return_value=True
            ), mock.patch.object(
                assistant_main.ui, "set_soul_payload"
            ) as set_soul, mock.patch.object(
                assistant_main.ui, "clear_trajectory_points"
            ), mock.patch.object(
                assistant_main.ui, "clear_spirit_readings"
            ):
                # machinesoul is independent of the semantic memory frame.
                assistant_main._update_hazard_trajectory("hello", False)
        finally:
            assistant_main._hazard_soul_payload = old

        set_soul.assert_called_once_with(payload)

    def test_the_lower_half_is_the_payload_bytes_not_a_picture_of_them(self):
        # machinesoul maps four-coordinate vectors onto RGBA. Four bytes in
        # must be one cell out, in written order, or this is decoration.
        payload = bytes([255, 0, 0, 255, 0, 255, 0, 255])
        field = vector_panel.Field()
        field.set_soul(payload)
        rows = field._render_soul(2, 1)

        self.assertEqual(len(rows), 1)
        self.assertEqual(len(rows[0]), 2)
        for char, style in rows[0]:
            self.assertNotEqual(char, " ")

    def test_a_short_payload_does_not_wrap_or_pad_with_invented_data(self):
        field = vector_panel.Field()
        field.set_soul(bytes([10, 20, 30, 40]))
        rows = field._render_soul(4, 1)

        drawn = [char for char, _ in rows[0] if char != " "]
        self.assertEqual(len(drawn), 1)

    def test_alpha_dims_a_cell_rather_than_being_discarded(self):
        # A fully transparent vector is still preserved data and has to stay
        # visible as data; dropping alpha would hide a coordinate.
        bright = vector_panel.Field()
        bright.set_soul(bytes([200, 200, 200, 255]))
        faint = vector_panel.Field()
        faint.set_soul(bytes([200, 200, 200, 0]))

        self.assertNotEqual(bright._render_soul(1, 1), faint._render_soul(1, 1))
        for char, _ in faint._render_soul(1, 1)[0]:
            self.assertNotEqual(char, " ")


class PanelFallbackTests(unittest.TestCase):
    def test_an_ordinary_session_renders_exactly_as_before(self):
        # Neither language supplied: the retrieval cloud and entropy strip
        # must be untouched, byte for byte.
        field = vector_panel.Field()
        field.set_memories([[1.0, 2.0, 3.0], [2.0, 1.0, 0.5], [0.2, 0.4, 0.9]])
        before = field.render_cells(40, 20)

        field.set_spirit(READINGS)
        field.set_soul(b"\x01\x02\x03\x04")
        self.assertNotEqual(field.render_cells(40, 20), before)

        field.clear_spirit()
        field.clear_soul()
        self.assertEqual(field.render_cells(40, 20), before)

    def test_either_language_alone_switches_the_panel(self):
        field = vector_panel.Field()
        field.set_memories([[1.0, 2.0], [0.5, 1.5]])
        cloud = field.render_cells(30, 16)

        field.set_spirit(READINGS)
        self.assertNotEqual(field.render_cells(30, 16), cloud)

        field.clear_spirit()
        field.set_soul(b"\xff\x00\x00\xff")
        self.assertNotEqual(field.render_cells(30, 16), cloud)


def _brightest(cells):
    """The highest colour channel anywhere in a rendered block."""
    best = 0
    for row in cells:
        for _, style in row:
            for triple in re.findall(r"[34]8;2;(\d+);(\d+);(\d+)", style):
                best = max(best, max(int(value) for value in triple))
    return best


class DisplayRangeTests(unittest.TestCase):
    """Both readouts measure 0..0.4 and were drawn as though they spanned 0..1.

    Measured live on 2026-07-30: entropy over ten candidates ran 0.00 to 0.39
    with a mean of 0.16, and anchor support peaked at 0.374. Against the
    theoretical maximum the strip's top 62% could not be reached by any token
    a real model produces, and the strongest anchor in a readout arrived at
    half brightness. Both now scale to the strongest value on screen.
    """

    def _lit_rows(self, cells, column, strip_rows):
        return sum(
            1 for row in cells[-strip_rows:] if row[column][0] != " "
        )

    def test_a_realistic_entropy_spread_uses_the_whole_strip(self):
        field = vector_panel.Field()
        # The shape of the live trace: mostly committed, one real fork.
        for level in (0.00, 0.05, 0.16, 0.39, 0.01, 0.28, 0.04, 0.00):
            field.entropy.append(level)

        cells = field.render_cells(8, 10, strip_rows=8)

        # Column 3 holds the peak, and the peak is what the strip is for.
        self.assertEqual(self._lit_rows(cells, 3, 8), 8)
        # The committed tokens stay near the floor -- scaling must not
        # flatten the difference it exists to show.
        self.assertLessEqual(self._lit_rows(cells, 0, 8), 1)

    def test_a_passage_with_no_forks_is_not_stretched_into_one(self):
        """The floor, doing the job the floor is there for."""
        field = vector_panel.Field()
        for _ in range(8):
            field.entropy.append(0.02)

        cells = field.render_cells(8, 10, strip_rows=8)

        # 0.02 read against the 0.12 floor, not against itself.
        self.assertLessEqual(self._lit_rows(cells, 0, 8), 2)

    def test_the_strongest_anchor_reaches_full_brightness(self):
        field = vector_panel.Field()
        field.set_spirit([
            (0, [(0.374, "a fire alarm during an exam")]),
            (1, [(0.30, "the silence after a loud noise")]),
        ])

        cells = field.render_cells(12, 10, strip_rows=4)

        # Absolutely scaled, 0.374 landed at 0.22 + 0.78 * 0.374 = 0.51 value,
        # which is the washed-out panel this replaces.
        self.assertGreaterEqual(_brightest(cells), 240)

    def test_a_readout_where_nothing_scored_stays_dim(self):
        field = vector_panel.Field()
        field.set_spirit([
            (0, [(0.05, "an anchor that barely matched")]),
            (1, [(0.04, "another that did not either")]),
        ])

        cells = field.render_cells(12, 10, strip_rows=4)

        # Read against the 0.20 floor. Weak matches must not be promoted into
        # a confident-looking reading just because they are the best present.
        self.assertLess(_brightest(cells), 200)


if __name__ == "__main__":
    unittest.main()
