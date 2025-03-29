import unittest
from unittest.mock import patch, MagicMock
import json
import os
import uuid
from io import StringIO
from typing import Tuple

# Import the module to test
import cronjob


class TestCronJob(unittest.TestCase):
    """Test suite for the cronjob module functionality."""

    def setUp(self) -> None:
        """Set up test environment and sample data for each test."""
        # Setup test data
        self.test_data = [
            {
                "uuid": "test-uuid-1",
                "chat_id": 123,
                "owner": 456,
                "hour": 13,
                "minute": 45,
                "command": "test_command_1",
            },
            {
                "uuid": "test-uuid-2",
                "chat_id": 789,
                "owner": 456,
                "hour": 14,
                "minute": 30,
                "command": "test_command_2",
            },
        ]

        # Mock environment variables
        self.env_patcher = patch.dict("os.environ", {"OWNERS_WHITELIST": "456,789"})
        self.env_patcher.start()

        # Store original whitelist and update it for testing
        self.original_whitelist = cronjob.OWNERS_WHITELIST
        cronjob.OWNERS_WHITELIST = [
            int(i)
            for i in os.environ.get("OWNERS_WHITELIST", "").replace(",", " ").split()
        ]

    def tearDown(self) -> None:
        """Clean up after tests."""
        self.env_patcher.stop()
        cronjob.OWNERS_WHITELIST = self.original_whitelist

    def _setup_file_mocks(
        self, read_data: str, write_data: StringIO
    ) -> Tuple[MagicMock, MagicMock]:
        """Helper method to set up file read/write mocks."""
        read_mock = MagicMock()
        if read_data:
            read_mock.read.return_value = read_data

        write_mock = MagicMock()
        if write_data:
            write_mock.write = write_data.write

        return read_mock, write_mock

    def test_parse_job(self) -> None:
        """Test job text parsing functionality."""
        command, hour, minute = cronjob.parse_job("/cron 13:45 test_command")

        self.assertEqual(command, "test_command", "Command was not parsed correctly")
        self.assertEqual(hour, 13, "Hour was not parsed correctly")
        self.assertEqual(minute, 45, "Minute was not parsed correctly")

    @patch("uuid.uuid4")
    @patch("builtins.open")
    def test_add_job_new_file(self, mock_open: MagicMock, mock_uuid: MagicMock) -> None:
        """Test adding a job when the jobs file doesn't exist."""
        mock_uuid.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")
        mock_open.side_effect = [FileNotFoundError, MagicMock()]

        result = cronjob.add_job("/cron 13:45 test_command", 123, 456)

        self.assertEqual(result, "12345678-1234-5678-1234-567812345678")
        self.assertEqual(
            mock_open.call_count, 2, "Open should be called twice (read + write)"
        )

    @patch("uuid.uuid4")
    @patch("builtins.open")
    def test_add_job_json_decode_error(
        self, mock_open: MagicMock, mock_uuid: MagicMock
    ) -> None:
        """Test adding a job when the jobs file contains invalid JSON."""
        mock_uuid.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")

        mock_cm = MagicMock()
        mock_cm.read.return_value = "invalid json"
        mock_open.return_value.__enter__.return_value = mock_cm

        result = cronjob.add_job("/cron 13:45 test_command", 123, 456)

        self.assertEqual(result, "12345678-1234-5678-1234-567812345678")
        self.assertTrue(mock_cm.write.called, "File write method should be called")

    @patch("uuid.uuid4")
    @patch("builtins.open")
    def test_add_job_existing_file(
        self, mock_open: MagicMock, mock_uuid: MagicMock
    ) -> None:
        """Test adding a job when the jobs file exists with valid content."""
        mock_uuid.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")
        written_data = StringIO()

        read_mock, write_mock = self._setup_file_mocks(
            read_data=json.dumps(self.test_data), write_data=written_data
        )

        mock_open.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=read_mock)),
            MagicMock(__enter__=MagicMock(return_value=write_mock)),
        ]

        result = cronjob.add_job("/cron 13:45 new_command", 123, 456)

        self.assertEqual(result, "12345678-1234-5678-1234-567812345678")

        written_data.seek(0)
        actual_data = json.loads(written_data.getvalue())

        expected_data = self.test_data + [
            {
                "uuid": "12345678-1234-5678-1234-567812345678",
                "chat_id": 123,
                "owner": 456,
                "hour": 13,
                "minute": 45,
                "command": "new_command",
            }
        ]

        self.assertEqual(actual_data, expected_data)

    @patch("builtins.open")
    def test_add_job_max_limit(self, mock_open: MagicMock) -> None:
        """Test adding a job when owner has reached the maximum job limit."""
        test_data = [
            {
                "uuid": f"test-uuid-{i}",
                "chat_id": 123,
                "owner": 456,
                "hour": 13,
                "minute": 45,
                "command": f"test_command_{i}",
            }
            for i in range(cronjob.MAX_JOBS_PER_OWNER)
        ]

        mock_cm = MagicMock()
        mock_cm.read.return_value = json.dumps(test_data)
        mock_open.return_value.__enter__.return_value = mock_cm

        with self.assertRaises(Exception) as context:
            cronjob.add_job("/cron 13:45 new_command", 123, 456)

        self.assertIn("IGNORE cron add", str(context.exception))

    @patch("builtins.open")
    def test_del_job_existing(self, mock_open: MagicMock) -> None:
        """Test deleting an existing job."""
        written_data = StringIO()

        read_mock, write_mock = self._setup_file_mocks(
            read_data=json.dumps(self.test_data), write_data=written_data
        )

        mock_open.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=read_mock)),
            MagicMock(__enter__=MagicMock(return_value=write_mock)),
        ]

        result = cronjob.del_job("/delcron test-uuid-1", 123, 456)

        self.assertTrue(result)

        written_data.seek(0)
        actual_data = json.loads(written_data.getvalue())
        expected_data = [job for job in self.test_data if job["uuid"] != "test-uuid-1"]

        self.assertEqual(actual_data, expected_data)

    @patch("builtins.open")
    def test_del_job_nonexistent(self, mock_open: MagicMock) -> None:
        """Test deleting a non-existent job."""
        written_data = StringIO()

        read_mock, write_mock = self._setup_file_mocks(
            read_data=json.dumps(self.test_data), write_data=written_data
        )

        mock_open.side_effect = [
            MagicMock(__enter__=MagicMock(return_value=read_mock)),
            MagicMock(__enter__=MagicMock(return_value=write_mock)),
        ]

        result = cronjob.del_job("/delcron nonexistent-uuid", 123, 456)

        self.assertTrue(result)
        written_data.seek(0)
        actual_data = json.loads(written_data.getvalue())

        self.assertEqual(actual_data, self.test_data)

    @patch("builtins.open")
    def test_list_job(self, mock_open: MagicMock) -> None:
        """Test listing jobs for a specific owner."""
        mock_cm = MagicMock()
        mock_cm.read.return_value = json.dumps(self.test_data)
        mock_open.return_value.__enter__.return_value = mock_cm

        # Test for owner with jobs
        result = cronjob.list_job("/listcron", 123, 456)

        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]["uuid"], "test-uuid-1")
        self.assertEqual(result[1]["uuid"], "test-uuid-2")

        # Test for owner with no jobs
        result = cronjob.list_job("/listcron", 123, 789)
        self.assertEqual(len(result), 0)

    @patch("datetime.datetime")
    @patch("builtins.open")
    def test_run_cron_match(
        self, mock_open: MagicMock, mock_datetime: MagicMock
    ) -> None:
        """Test running cron when time matches a job."""
        mock_cm = MagicMock()
        mock_cm.read.return_value = json.dumps(self.test_data)
        mock_open.return_value.__enter__.return_value = mock_cm

        mock_now = MagicMock()
        mock_now.hour = 13
        mock_now.minute = 45
        mock_datetime.now.return_value = mock_now

        mock_dispatch = MagicMock()
        cronjob.run_cron(mock_dispatch)

        mock_dispatch.assert_called_once_with("test_command_1", 123, 456)

    @patch("datetime.datetime")
    @patch("builtins.open")
    def test_run_cron_no_match(
        self, mock_open: MagicMock, mock_datetime: MagicMock
    ) -> None:
        """Test running cron when time doesn't match any job."""
        mock_cm = MagicMock()
        mock_cm.read.return_value = json.dumps(self.test_data)
        mock_open.return_value.__enter__.return_value = mock_cm

        mock_now = MagicMock()
        mock_now.hour = 12
        mock_now.minute = 0
        mock_datetime.now.return_value = mock_now

        mock_dispatch = MagicMock()
        cronjob.run_cron(mock_dispatch)

        mock_dispatch.assert_not_called()

    @patch("datetime.datetime")
    @patch("builtins.open")
    def test_run_cron_ignore_cron_commands(
        self, mock_open: MagicMock, mock_datetime: MagicMock
    ) -> None:
        """Test running cron ignores commands starting with 'cron'."""
        test_data = [
            {
                "uuid": "test-uuid-3",
                "chat_id": 123,
                "owner": 456,
                "hour": 13,
                "minute": 45,
                "command": "/cron 13:45 nested_command",
            }
        ]

        mock_cm = MagicMock()
        mock_cm.read.return_value = json.dumps(test_data)
        mock_open.return_value.__enter__.return_value = mock_cm

        mock_now = MagicMock()
        mock_now.hour = 13
        mock_now.minute = 45
        mock_datetime.now.return_value = mock_now

        mock_dispatch = MagicMock()
        cronjob.run_cron(mock_dispatch)

        mock_dispatch.assert_not_called()

    @patch("builtins.open")
    def test_file_not_found_handling(self, mock_open: MagicMock) -> None:
        """Test handling of FileNotFoundError in various methods."""
        # Test list_job
        mock_open.side_effect = FileNotFoundError
        result = cronjob.list_job("/listcron", 123, 456)
        self.assertEqual(result, [])

        # Reset mock for del_job test
        mock_open.reset_mock()
        mock_open.side_effect = [FileNotFoundError, MagicMock()]
        self.assertTrue(cronjob.del_job("/delcron test-uuid", 123, 456))

        # Reset mock for run_cron test
        mock_open.reset_mock()
        mock_open.side_effect = FileNotFoundError
        mock_dispatch = MagicMock()
        cronjob.run_cron(mock_dispatch)
        mock_dispatch.assert_not_called()


if __name__ == "__main__":
    unittest.main()
