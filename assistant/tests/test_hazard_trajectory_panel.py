"""Pure checks for the HazardSable token-path display boundary."""

import unittest
from unittest import mock

import main as assistant_main
from ui import vector_panel


class HazardTrajectoryPanelTests(unittest.TestCase):
    def setUp(self):
        self.memories = [
            [1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0],
            [-1.0, -1.0, -1.0],
        ]

    def test_path_uses_the_memory_frame_and_keeps_ordered_markers(self):
        field = vector_panel.Field()
        field.set_memories(self.memories)

        self.assertTrue(field.set_trajectory(self.memories[:3]))
        self.assertEqual(len(field.trajectory), 3)
        self.assertLess(field.trajectory[0]["hue"], field.trajectory[-1]["hue"])
        self.assertTrue(all(0.0 <= point["fidelity"] <= 1.0
                            for point in field.trajectory))

    def test_mismatched_dimensions_refuse_instead_of_drawing_a_false_path(self):
        field = vector_panel.Field()
        field.set_memories(self.memories)

        self.assertFalse(field.set_trajectory([[1.0, 0.0]]))
        self.assertEqual(field.trajectory, [])

    def test_lexical_panel_frame_never_requests_a_hazard_vector(self):
        with mock.patch.object(
            assistant_main.ui, "clear_trajectory_points"
        ) as clear, mock.patch.object(
            assistant_main.ui, "panel_active", return_value=True
        ), mock.patch.object(
            assistant_main.command_handlers, "is_experimental_mode", return_value=True
        ):
            assistant_main._update_hazard_trajectory("text", semantic_ready=False)

        clear.assert_called_once_with()


if __name__ == "__main__":
    unittest.main()
