"""The panel shows the two languages, and cannot contradict either one.

A panel that renders beautifully and disagrees with the instrument it claims
to show is worse than no panel. These hold the two agreements: machinespirit
above must be what `trace` prints, and machinesoul below must be the bytes a
capsule actually stores.
"""

import unittest
from unittest import mock

from core import machinespirit
from ui import vector_panel


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


if __name__ == "__main__":
    unittest.main()
