from __future__ import annotations

import unittest
from unittest.mock import patch, MagicMock, PropertyMock
from pathlib import Path


class TestCameraCapture(unittest.TestCase):
    """vision.camera_capture — CameraCapture sinifi."""

    def test_module_import(self):
        from vision import camera_capture
        self.assertIsNotNone(camera_capture)

    def test_default_attributes(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        cam.camera_id = 0
        cam.width = 640
        cam.height = 480
        cam._cap = None
        cam._is_open = False
        self.assertEqual(cam.camera_id, 0)
        self.assertEqual(cam.width, 640)
        self.assertEqual(cam.height, 480)
        self.assertFalse(cam._is_open)
        self.assertIsNone(cam._cap)

    def test_is_open_property(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        cam._is_open = False
        self.assertFalse(cam.is_open)
        cam._is_open = True
        self.assertTrue(cam.is_open)

    def test_open_when_already_open(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        cam._is_open = True
        result = cam.open()
        self.assertTrue(result)

    def test_open_import_error(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        cam._is_open = False
        with patch.dict("sys.modules", {"cv2": None}):
            result = cam.open()
            self.assertFalse(result)

    def test_open_cv2_fails(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        cam._is_open = False
        mock_cv2 = MagicMock()
        mock_cv2.VideoCapture.return_value.isOpened.return_value = False
        with patch.dict("sys.modules", {"cv2": mock_cv2}):
            result = cam.open()
            self.assertFalse(result)

    def test_open_cv2_succeeds(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        cam._is_open = False
        cam.camera_id = 0
        cam.width = 640
        cam.height = 480
        mock_cap = MagicMock()
        mock_cap.isOpened.return_value = True
        mock_cv2 = MagicMock()
        mock_cv2.VideoCapture.return_value = mock_cap
        with patch.dict("sys.modules", {"cv2": mock_cv2}):
            result = cam.open()
            self.assertTrue(result)
            self.assertTrue(cam._is_open)

    def test_close_releases_capture(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        mock_cap = MagicMock()
        cam._cap = mock_cap
        cam._is_open = True
        cam.close()
        mock_cap.release.assert_called_once()
        self.assertIsNone(cam._cap)
        self.assertFalse(cam._is_open)

    def test_close_without_cap(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        cam._cap = None
        cam._is_open = False
        cam.close()
        self.assertIsNone(cam._cap)

    def test_capture_not_open_fails(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        cam._is_open = False
        with patch.object(cam, "open", return_value=False):
            result = cam.capture()
            self.assertIsNone(result)

    def test_capture_retry_open_and_succeed(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        cam._is_open = False
        cam._cap = MagicMock()
        mock_cv2 = MagicMock()
        mock_cv2.imencode.return_value = (True, MagicMock())
        mock_cv2.imencode.return_value[1].tobytes.return_value = b"jpegdata"
        with patch.object(cam, "open", return_value=True):
            with patch.dict("sys.modules", {"cv2": mock_cv2}):
                cam._cap.read.return_value = (True, MagicMock())
                result = cam.capture()
                self.assertEqual(result, b"jpegdata")

    def test_capture_no_frame(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        cam._is_open = True
        cam._cap = MagicMock()
        cam._cap.read.return_value = (False, None)
        result = cam.capture()
        self.assertIsNone(result)

    def test_capture_to_file_writes_bytes(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        cam._is_open = True
        with patch.object(cam, "capture", return_value=b"jpegdata"):
            with patch("pathlib.Path.write_bytes") as mock_write:
                result = cam.capture_to_file("test.jpg")
                self.assertIn("test.jpg", result or "")
                mock_write.assert_called_once_with(b"jpegdata")

    def test_capture_to_file_no_bytes(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        with patch.object(cam, "capture", return_value=None):
            result = cam.capture_to_file()
            self.assertIsNone(result)

    def test_get_stats_structure(self):
        from vision.camera_capture import CameraCapture
        cam = CameraCapture.__new__(CameraCapture)
        cam.camera_id = 1
        cam.width = 1280
        cam.height = 720
        cam._is_open = True
        stats = cam.get_stats()
        self.assertEqual(stats["camera_id"], 1)
        self.assertEqual(stats["resolution"], "1280x720")
        self.assertTrue(stats["is_open"])
        self.assertIsInstance(stats["capture_dir"], str)

    def test_create_camera_capture_factory(self):
        from vision.camera_capture import create_camera_capture, CameraCapture
        cam = create_camera_capture(camera_id=2)
        self.assertIsInstance(cam, CameraCapture)
        self.assertEqual(cam.camera_id, 2)
