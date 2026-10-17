"""Guard original-image alignment and strict face count during scale fallback."""
import runtime
import unittest
from unittest.mock import Mock
import numpy as np
from engine import Models, InputError


def face_row():
    return np.array([[40, 50, 100, 140, 60, 70, 120, 70, 90, 100, 65, 135, 115, 135, .93]], dtype=np.float32)


class FaceScaleTests(unittest.TestCase):
    def models(self, detections):
        model = Models()
        model.detector = Mock()
        model.detector.detect.side_effect = [(None, faces) for faces in detections]
        model.recognizer = Mock()
        model.recognizer.alignCrop.return_value = np.zeros((112, 112, 3), dtype=np.uint8)
        model.recognizer.feature.return_value = np.ones((1, 128), dtype=np.float32)
        return model

    def test_successful_original_detection_is_unchanged(self):
        image = np.zeros((1192, 1081, 3), dtype=np.uint8)
        rows = face_row(); model = self.models([rows])
        face, _, feature = model._face_upright(image)
        np.testing.assert_array_equal(face, rows[0])
        self.assertEqual(model.detector.detect.call_count, 1)
        self.assertIs(model.recognizer.alignCrop.call_args.args[0], image)
        self.assertFalse(np.shares_memory(feature, model.recognizer.feature.return_value))

    def test_fallback_maps_box_and_landmarks_to_original_image(self):
        image = np.zeros((1192, 1081, 3), dtype=np.uint8)
        rows = face_row(); model = self.models([None, rows])
        face, _, _ = model._face_upright(image)
        expected = rows[0].copy()
        expected[:14:2] *= 1081 / 580
        expected[1:14:2] *= 1192 / 640
        np.testing.assert_allclose(face, expected)
        np.testing.assert_array_equal(rows, face_row())
        self.assertIs(model.recognizer.alignCrop.call_args.args[0], image)
        self.assertEqual(model.detector.detect.call_args_list[1].args[0].shape[:2], (640, 580))

    def test_second_fallback_can_detect_a_close_up(self):
        model = self.models([None, None, face_row()])
        model._face_upright(np.zeros((1200, 1000, 3), dtype=np.uint8))
        self.assertEqual(model.detector.detect.call_count, 3)
        self.assertEqual(model.detector.detect.call_args_list[-1].args[0].shape[:2], (320, 267))

    def test_multiple_faces_are_rejected_without_smaller_retry(self):
        for detections in ([np.repeat(face_row(), 2, axis=0)], [None, np.repeat(face_row(), 2, axis=0)]):
            with self.subTest(attempt=len(detections)):
                model = self.models(detections)
                with self.assertRaisesRegex(InputError, 'đúng một'):
                    model._face_upright(np.zeros((1200, 1000, 3), dtype=np.uint8))
                self.assertEqual(model.detector.detect.call_count, len(detections))
                model.recognizer.alignCrop.assert_not_called()

    def test_empty_input_detections_do_not_get_a_feature(self):
        model = self.models([None, np.empty((0, 15), np.float32), None])
        with self.assertRaisesRegex(InputError, 'Chưa tìm'):
            model._face_upright(np.zeros((1200, 1000, 3), dtype=np.uint8))
        model.recognizer.feature.assert_not_called()

    def test_small_images_are_never_upscaled_or_repeated(self):
        model = self.models([None])
        with self.assertRaises(InputError):
            model._face_upright(np.zeros((300, 200, 3), dtype=np.uint8))
        self.assertEqual(model.detector.detect.call_count, 1)
        model = self.models([None, None])
        with self.assertRaises(InputError):
            model._face_upright(np.zeros((640, 500, 3), dtype=np.uint8))
        self.assertEqual(model.detector.detect.call_count, 2)

    def test_tiny_face_is_still_rejected_in_original_coordinates(self):
        rows = face_row(); rows[0, 2:4] = 5
        model = self.models([None, rows])
        with self.assertRaisesRegex(InputError, 'quá nhỏ'):
            model._face_upright(np.zeros((1200, 1000, 3), dtype=np.uint8))


if __name__ == '__main__':
    unittest.main(verbosity=2)
