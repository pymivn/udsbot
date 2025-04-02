import unittest
from unittest.mock import patch, MagicMock
import os
import uuid
import datetime

# Import the module to test
import cronjob


class TestCronJob(unittest.TestCase):
    """Test suite for the SQLite3-based cronjob module functionality."""

    def setUp(self) -> None:
        """Set up test environment and sample data for each test."""
        # Test jobs data
        self.test_data = [
            ("test-uuid-1", 123, 456, 13, 45, "test_command_1"),
            ("test-uuid-2", 789, 456, 14, 30, "test_command_2"),
        ]

        # Mock environment variables
        self.env_patcher = patch.dict("os.environ", {"OWNERS_WHITELIST": "456,789"})
        self.env_patcher.start()

        # Delete test database if exists
        if os.path.exists(cronjob.DB_FILE):
            os.remove(cronjob.DB_FILE)

    def tearDown(self) -> None:
        """Clean up after tests."""
        self.env_patcher.stop()

        # Clean up test database
        if os.path.exists(cronjob.DB_FILE):
            os.remove(cronjob.DB_FILE)

    def test_parse_job(self) -> None:
        """Test job text parsing functionality."""
        command, hour, minute = cronjob.parse_job("/cron 13:45 test_command")
        self.assertEqual(command, "test_command", "Command was not parsed correctly")
        self.assertEqual(hour, 13, "Hour was not parsed correctly")
        self.assertEqual(minute, 45, "Minute was not parsed correctly")

    @patch("sqlite3.connect")
    @patch("uuid.uuid4")
    def test_add_job(self, mock_uuid: MagicMock, mock_connect: MagicMock) -> None:
        """Test adding a job to the database."""
        # Set up mocks
        mock_uuid.return_value = uuid.UUID("12345678-1234-5678-1234-567812345678")
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (0,)  # No existing jobs

        # Call function
        result = cronjob.add_job("/cron 13:45 test_command", 123, 456)

        # Assertions
        self.assertEqual(result, "12345678-1234-5678-1234-567812345678")
        mock_connect.assert_called_with(cronjob.DB_FILE)
        mock_cursor.execute.assert_any_call(
            "SELECT COUNT(*) FROM jobs WHERE owner = ?", (456,)
        )
        mock_cursor.execute.assert_any_call(
            "INSERT INTO jobs (uuid, chat_id, owner, hour, minute, command) VALUES (?, ?, ?, ?, ?, ?)",
            ("12345678-1234-5678-1234-567812345678", 123, 456, 13, 45, "test_command"),
        )
        mock_conn.commit.assert_called()
        mock_conn.close.assert_called()

    @patch("sqlite3.connect")
    def test_add_job_max_limit(self, mock_connect: MagicMock) -> None:
        """Test adding a job when owner has reached the maximum job limit."""
        # Set up mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchone.return_value = (
            cronjob.MAX_JOBS_PER_OWNER,
        )  # Max jobs reached

        # Call function and check exception
        with self.assertRaises(Exception) as context:
            cronjob.add_job("/cron 13:45 new_command", 123, 456)
        self.assertIn("IGNORE cron add", str(context.exception))
        mock_conn.close.assert_called()

    @patch("sqlite3.connect")
    def test_del_job(self, mock_connect: MagicMock) -> None:
        """Test deleting a job from the database."""
        # Set up mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Call function
        result = cronjob.del_job("/delcron test-uuid-1", 123, 456)

        # Assertions
        self.assertTrue(result)
        mock_cursor.execute.assert_any_call(
            "DELETE FROM jobs WHERE uuid = ? AND owner = ?", ("test-uuid-1", 456)
        )
        mock_conn.commit.assert_called()
        mock_conn.close.assert_called()

    @patch("sqlite3.connect")
    def test_list_job(self, mock_connect: MagicMock) -> None:
        """Test listing jobs for a specific owner."""
        # Set up mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Mock row factory results
        mock_rows = [MagicMock(spec=dict), MagicMock(spec=dict)]
        mock_rows[0].__getitem__.side_effect = lambda k: {
            "uuid": "test-uuid-1",
            "chat_id": 123,
            "owner": 456,
            "hour": 13,
            "minute": 45,
            "command": "test_command_1",
        }[k]
        mock_rows[1].__getitem__.side_effect = lambda k: {
            "uuid": "test-uuid-2",
            "chat_id": 789,
            "owner": 456,
            "hour": 14,
            "minute": 30,
            "command": "test_command_2",
        }[k]

        mock_cursor.fetchall.return_value = mock_rows

        # Call function
        result = cronjob.list_job("/listcron", 123, 456)

        # Assertions
        self.assertEqual(len(result), 2)
        mock_cursor.execute.assert_called_with(
            "SELECT uuid, chat_id, owner, hour, minute, command FROM jobs WHERE owner = ?",
            (456,),
        )
        mock_conn.close.assert_called()

    @patch("sqlite3.connect")
    def test_list_job_no_jobs(self, mock_connect: MagicMock) -> None:
        """Test listing jobs when owner has no jobs."""
        # Set up mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = []

        # Call function
        result = cronjob.list_job("/listcron", 123, 789)

        # Assertions
        self.assertEqual(len(result), 0)
        mock_cursor.execute.assert_called_with(
            "SELECT uuid, chat_id, owner, hour, minute, command FROM jobs WHERE owner = ?",
            (789,),
        )
        mock_conn.close.assert_called()

    @patch("datetime.datetime")
    @patch("sqlite3.connect")
    def test_run_cron_match(
        self, mock_connect: MagicMock, mock_datetime: MagicMock
    ) -> None:
        """Test running cron when time matches a job."""
        # Set up mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = self.test_data

        # Mock datetime to match first job
        mock_now = MagicMock()
        mock_now.hour = 13
        mock_now.minute = 45
        mock_datetime.now.return_value = mock_now
        mock_datetime.UTC = datetime.UTC

        # Call function
        mock_dispatch = MagicMock()
        cronjob.run_cron(mock_dispatch)

        # Assertions
        mock_dispatch.assert_called_once_with("test_command_1", 123, 456)

    @patch("datetime.datetime")
    @patch("sqlite3.connect")
    def test_run_cron_no_match(
        self, mock_connect: MagicMock, mock_datetime: MagicMock
    ) -> None:
        """Test running cron when time doesn't match any job."""
        # Set up mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = self.test_data

        # Mock datetime with non-matching time
        mock_now = MagicMock()
        mock_now.hour = 12
        mock_now.minute = 0
        mock_datetime.now.return_value = mock_now
        mock_datetime.UTC = datetime.UTC

        # Call function
        mock_dispatch = MagicMock()
        cronjob.run_cron(mock_dispatch)

        # Assertions
        mock_dispatch.assert_not_called()

    @patch("datetime.datetime")
    @patch("sqlite3.connect")
    def test_run_cron_ignore_cron_commands(
        self, mock_connect: MagicMock, mock_datetime: MagicMock
    ) -> None:
        """Test running cron ignores commands starting with 'cron'."""
        # Set up mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor
        mock_cursor.fetchall.return_value = [
            ("test-uuid-3", 123, 456, 13, 45, "/cron 13:45 nested_command")
        ]

        # Mock datetime to match job time
        mock_now = MagicMock()
        mock_now.hour = 13
        mock_now.minute = 45
        mock_datetime.now.return_value = mock_now
        mock_datetime.UTC = datetime.UTC

        # Call function
        mock_dispatch = MagicMock()
        cronjob.run_cron(mock_dispatch)

        # Assertions
        mock_dispatch.assert_not_called()

    @patch("sqlite3.connect")
    def test_init_db(self, mock_connect: MagicMock) -> None:
        """Test database initialization."""
        # Set up mocks
        mock_conn = MagicMock()
        mock_cursor = MagicMock()
        mock_connect.return_value = mock_conn
        mock_conn.cursor.return_value = mock_cursor

        # Call function
        cronjob.init_db()

        # Assertions
        mock_cursor.execute.assert_called_with("""
    CREATE TABLE IF NOT EXISTS jobs (
        uuid TEXT PRIMARY KEY,
        chat_id INTEGER,
        owner INTEGER,
        hour INTEGER,
        minute INTEGER,
        command TEXT
    )
    """)
        mock_conn.commit.assert_called()
        mock_conn.close.assert_called()


if __name__ == "__main__":
    unittest.main()
