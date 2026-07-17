import unittest
from unittest.mock import patch, mock_open
import sys

# Add src folder to sys.path to allow running python -m unittest tests/test_main.py directly
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "../src")))

from s3_cleanup.main import (
    get_required_arg,
    get_arg_with_default,
    parse_list_file,
)


class TestS3CleanupMain(unittest.TestCase):

    @patch("builtins.input", return_value="test-value")
    def test_get_required_arg_with_input(self, mock_input):
        result = get_required_arg(None, "Enter value: ", "Error msg")
        self.assertEqual(result, "test-value")

    def test_get_required_arg_already_provided(self):
        result = get_required_arg("existing-value", "Enter value: ", "Error msg")
        self.assertEqual(result, "existing-value")

    @patch("builtins.input", return_value="")
    def test_get_arg_with_default_empty_input(self, mock_input):
        result = get_arg_with_default(None, "Enter value", "default-value")
        self.assertEqual(result, "default-value")

    @patch("builtins.input", return_value="user-override")
    def test_get_arg_with_default_override(self, mock_input):
        result = get_arg_with_default(None, "Enter value", "default-value")
        self.assertEqual(result, "user-override")

    def test_parse_list_file_success(self):
        mock_file_content = (
            "LastModified | Size (MB) | Object Key\n"
            "--------------------------------------------------------------------------------\n"
            "2026-06-30T12:00:00Z | 15.50 MB | network/folder/file1.log\n"
            "2026-07-01T08:30:00Z | 20.00 MB | network/folder/file2.log\n"
        )

        with patch("builtins.open", mock_open(read_data=mock_file_content)):
            header, data = parse_list_file("dummy_path.txt")

            self.assertEqual(len(header), 2)
            self.assertEqual(len(data), 2)

            self.assertEqual(data[0]["date"], "2026-06-30T12:00:00Z")
            self.assertEqual(data[0]["size"], 15.50)
            self.assertEqual(data[0]["key"], "network/folder/file1.log")

            self.assertEqual(data[1]["date"], "2026-07-01T08:30:00Z")
            self.assertEqual(data[1]["size"], 20.00)
            self.assertEqual(data[1]["key"], "network/folder/file2.log")

    @patch("sys.exit")
    def test_parse_list_file_not_found(self, mock_exit):
        parse_list_file("non_existent_file.txt")
        mock_exit.assert_called_once_with(1)


if __name__ == "__main__":
    unittest.main()
