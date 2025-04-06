import unittest
from unittest.mock import patch, MagicMock, call
import os
import uuid
import datetime
import sqlite3
import json
import tempfile
import shutil

# Import the module to test
import cronjob
from cronjob import (
    parse_job,
    add_job,
    del_job,
    list_job,
    run_cron,
    SQLStorage,
    JSONStorage,
    Job,
    MaxJobsReachedError,
    MAX_JOBS_PER_OWNER,
)


class TestParseJob(unittest.TestCase):
    """Tests for the parse_job function."""

    def test_valid_parsing(self):
        """Test parsing valid job strings."""
        command, hour, minute = parse_job("/cron 13:45 test command")
        self.assertEqual(command, "test command")
        self.assertEqual(hour, 13)
        self.assertEqual(minute, 45)

        command, hour, minute = parse_job("/addcron 0:0 another command")
        self.assertEqual(command, "another command")
        self.assertEqual(hour, 0)
        self.assertEqual(minute, 0)

        command, hour, minute = parse_job("/cron  8 : 5  spaced command ")
        self.assertEqual(command, "spaced command")
        self.assertEqual(hour, 8)
        self.assertEqual(minute, 5)

    def test_invalid_format(self):
        """Test parsing invalid job strings."""
        with self.assertRaisesRegex(ValueError, "Invalid job format"):
            parse_job("/cron 1345 test command")
        with self.assertRaisesRegex(ValueError, "Invalid job format"):
            parse_job("/cron 13:45") # Missing command
        with self.assertRaisesRegex(ValueError, "Invalid job format"):
            parse_job("cron 13:45 test command") # Missing /
        with self.assertRaisesRegex(ValueError, "Invalid job format"):
            parse_job("/cron test command") # Missing time

    def test_invalid_time(self):
        """Test parsing job strings with invalid times."""
        with self.assertRaisesRegex(ValueError, "Invalid time format"):
            parse_job("/cron 24:00 test command")
        with self.assertRaisesRegex(ValueError, "Invalid time format"):
            parse_job("/cron 10:60 test command")
        # This case fails the regex format check first, not the time range check
        with self.assertRaisesRegex(ValueError, "Invalid job format"):
            parse_job("/cron -1:30 test command")


class TestSQLStorage(unittest.TestCase):
    """Tests for the SQLStorage implementation."""

    def setUp(self):
        """Create a temporary database file."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_file = os.path.join(self.temp_dir, "test_cronjobs.db")
        self.storage = SQLStorage(self.db_file)
        # Ensure clean state
        if os.path.exists(self.db_file):
            os.remove(self.db_file)
        self.storage.init_db() # Initialize schema

    def tearDown(self):
        """Remove the temporary database file and directory."""
        shutil.rmtree(self.temp_dir)

    def test_init_db_creates_table(self):
        """Test if init_db creates the jobs table."""
        # Check if table exists
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='jobs';")
            self.assertIsNotNone(cursor.fetchone())

    def test_add_and_list_job(self):
        """Test adding and listing jobs."""
        job_uuid = str(uuid.uuid4())
        self.storage.add_job(job_uuid, 123, 456, 10, 30, "command1")
        jobs = self.storage.list_jobs(456)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["uuid"], job_uuid)
        self.assertEqual(jobs[0]["owner"], 456)
        self.assertEqual(jobs[0]["command"], "command1")

        # List for another owner
        jobs_other = self.storage.list_jobs(789)
        self.assertEqual(len(jobs_other), 0)

    def test_add_job_max_limit(self):
        """Test adding jobs up to the maximum limit."""
        owner_id = 789
        for i in range(MAX_JOBS_PER_OWNER):
            job_uuid = str(uuid.uuid4())
            self.storage.add_job(job_uuid, 123, owner_id, 11, i, f"command_{i}")

        # Try adding one more
        with self.assertRaises(MaxJobsReachedError):
            self.storage.add_job(str(uuid.uuid4()), 123, owner_id, 12, 0, "command_over_limit")

        # Verify count
        jobs = self.storage.list_jobs(owner_id)
        self.assertEqual(len(jobs), MAX_JOBS_PER_OWNER)

    def test_del_job(self):
        """Test deleting a job."""
        job_uuid1 = str(uuid.uuid4())
        job_uuid2 = str(uuid.uuid4())
        owner1 = 456
        owner2 = 789
        self.storage.add_job(job_uuid1, 123, owner1, 10, 30, "command1")
        self.storage.add_job(job_uuid2, 123, owner2, 11, 00, "command2")

        # Delete job belonging to owner1
        deleted = self.storage.del_job(job_uuid1, owner1)
        self.assertTrue(deleted)
        self.assertEqual(len(self.storage.list_jobs(owner1)), 0)
        self.assertEqual(len(self.storage.list_jobs(owner2)), 1) # Owner2's job remains

        # Try deleting already deleted job
        deleted_again = self.storage.del_job(job_uuid1, owner1)
        self.assertFalse(deleted_again)

        # Try deleting job belonging to another owner
        deleted_wrong_owner = self.storage.del_job(job_uuid2, owner1)
        self.assertFalse(deleted_wrong_owner)
        self.assertEqual(len(self.storage.list_jobs(owner2)), 1) # Owner2's job still remains

    def test_get_due_jobs(self):
        """Test retrieving jobs due at a specific time."""
        uuid1 = str(uuid.uuid4())
        uuid2 = str(uuid.uuid4())
        uuid3 = str(uuid.uuid4())
        self.storage.add_job(uuid1, 100, 200, 14, 30, "cmd1")
        self.storage.add_job(uuid2, 101, 201, 14, 30, "cmd2")
        self.storage.add_job(uuid3, 102, 202, 15, 00, "cmd3")

        due_jobs = self.storage.get_due_jobs(14, 30)
        self.assertEqual(len(due_jobs), 2)
        due_uuids = {job["uuid"] for job in due_jobs}
        self.assertIn(uuid1, due_uuids)
        self.assertIn(uuid2, due_uuids)

        due_jobs_none = self.storage.get_due_jobs(16, 00)
        self.assertEqual(len(due_jobs_none), 0)


class TestJSONStorage(unittest.TestCase):
    """Tests for the JSONStorage implementation."""

    def setUp(self):
        """Create a temporary JSON file."""
        self.temp_dir = tempfile.mkdtemp()
        self.json_file = os.path.join(self.temp_dir, "test_cronjobs.json")
        self.storage = JSONStorage(self.json_file)
        # Ensure clean state
        if os.path.exists(self.json_file):
            os.remove(self.json_file)
        self.storage.init_db() # Initialize file

    def tearDown(self):
        """Remove the temporary JSON file and directory."""
        shutil.rmtree(self.temp_dir)

    def test_init_db_creates_file(self):
        """Test if init_db creates the JSON file with an empty list."""
        self.assertTrue(os.path.exists(self.json_file))
        with open(self.json_file, 'r') as f:
            content = json.load(f)
            self.assertEqual(content, [])

    def test_init_db_existing_file(self):
        """Test init_db doesn't overwrite an existing valid JSON file."""
        initial_data = [{"test": "data"}]
        with open(self.json_file, 'w') as f:
            json.dump(initial_data, f)
        self.storage.init_db() # Should not raise error or clear file
        with open(self.json_file, 'r') as f:
            content = json.load(f)
            self.assertEqual(content, initial_data)

    def test_add_and_list_job(self):
        """Test adding and listing jobs."""
        job_uuid = str(uuid.uuid4())
        self.storage.add_job(job_uuid, 123, 456, 10, 30, "command1")
        jobs = self.storage.list_jobs(456)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["uuid"], job_uuid)
        self.assertEqual(jobs[0]["owner"], 456)
        self.assertEqual(jobs[0]["command"], "command1")

        # List for another owner
        jobs_other = self.storage.list_jobs(789)
        self.assertEqual(len(jobs_other), 0)

    def test_add_job_max_limit(self):
        """Test adding jobs up to the maximum limit."""
        owner_id = 789
        for i in range(MAX_JOBS_PER_OWNER):
            job_uuid = str(uuid.uuid4())
            self.storage.add_job(job_uuid, 123, owner_id, 11, i, f"command_{i}")

        # Try adding one more
        with self.assertRaises(MaxJobsReachedError):
            self.storage.add_job(str(uuid.uuid4()), 123, owner_id, 12, 0, "command_over_limit")

        # Verify count
        jobs = self.storage.list_jobs(owner_id)
        self.assertEqual(len(jobs), MAX_JOBS_PER_OWNER)

    def test_del_job(self):
        """Test deleting a job."""
        job_uuid1 = str(uuid.uuid4())
        job_uuid2 = str(uuid.uuid4())
        owner1 = 456
        owner2 = 789
        self.storage.add_job(job_uuid1, 123, owner1, 10, 30, "command1")
        self.storage.add_job(job_uuid2, 123, owner2, 11, 00, "command2")

        # Delete job belonging to owner1
        deleted = self.storage.del_job(job_uuid1, owner1)
        self.assertTrue(deleted)
        self.assertEqual(len(self.storage.list_jobs(owner1)), 0)
        self.assertEqual(len(self.storage.list_jobs(owner2)), 1) # Owner2's job remains

        # Try deleting already deleted job
        deleted_again = self.storage.del_job(job_uuid1, owner1)
        self.assertFalse(deleted_again)

        # Try deleting job belonging to another owner
        deleted_wrong_owner = self.storage.del_job(job_uuid2, owner1)
        self.assertFalse(deleted_wrong_owner)
        self.assertEqual(len(self.storage.list_jobs(owner2)), 1) # Owner2's job still remains

    def test_get_due_jobs(self):
        """Test retrieving jobs due at a specific time."""
        uuid1 = str(uuid.uuid4())
        uuid2 = str(uuid.uuid4())
        uuid3 = str(uuid.uuid4())
        self.storage.add_job(uuid1, 100, 200, 14, 30, "cmd1")
        self.storage.add_job(uuid2, 101, 201, 14, 30, "cmd2")
        self.storage.add_job(uuid3, 102, 202, 15, 00, "cmd3")

        due_jobs = self.storage.get_due_jobs(14, 30)
        self.assertEqual(len(due_jobs), 2)
        due_uuids = {job["uuid"] for job in due_jobs}
        self.assertIn(uuid1, due_uuids)
        self.assertIn(uuid2, due_uuids)

        due_jobs_none = self.storage.get_due_jobs(16, 00)
        self.assertEqual(len(due_jobs_none), 0)


# Patch the storage instance used by the cronjob module functions
@patch('cronjob.storage', new_callable=MagicMock)
class TestCronJobLogic(unittest.TestCase):
    """Tests for the core cronjob logic (add, del, list, run) with mocked storage."""

    def test_add_job_success(self, mock_storage):
        """Test successful job addition."""
        test_uuid = "test-uuid-123"
        with patch('uuid.uuid4', return_value=test_uuid):
            result_uuid = add_job("/cron 10:30 test command", 123, 456)

        self.assertEqual(result_uuid, test_uuid)
        mock_storage.add_job.assert_called_once_with(
            test_uuid, 123, 456, 10, 30, "test command"
        )

    def test_add_job_parsing_error(self, mock_storage):
        """Test add_job handling parse errors."""
        with self.assertRaises(ValueError):
            add_job("/cron invalid time", 123, 456)
        mock_storage.add_job.assert_not_called()

    def test_add_job_storage_error(self, mock_storage):
        """Test add_job handling storage errors (MaxJobsReachedError)."""
        mock_storage.add_job.side_effect = MaxJobsReachedError("Limit reached")
        with self.assertRaises(MaxJobsReachedError):
             add_job("/cron 11:00 another command", 123, 456)
        mock_storage.add_job.assert_called_once() # Ensure it was called

    def test_del_job_success(self, mock_storage):
        """Test successful job deletion."""
        mock_storage.del_job.return_value = True
        result = del_job("/delcron job-to-delete-uuid", 123, 456)
        self.assertTrue(result)
        mock_storage.del_job.assert_called_once_with("job-to-delete-uuid", 456)

    def test_del_job_not_found(self, mock_storage):
        """Test deleting a non-existent job or job owned by another."""
        mock_storage.del_job.return_value = False
        result = del_job("/delcron non-existent-uuid", 123, 456)
        self.assertFalse(result)
        mock_storage.del_job.assert_called_once_with("non-existent-uuid", 456)

    def test_del_job_invalid_format(self, mock_storage):
        """Test del_job handling invalid command format."""
        with self.assertRaisesRegex(ValueError, "Invalid delete format"):
            del_job("/delcron", 123, 456) # Missing UUID
        with self.assertRaisesRegex(ValueError, "Invalid delete format"):
            del_job("/delcron ", 123, 456) # Missing UUID (space only)
        mock_storage.del_job.assert_not_called()

    def test_list_job_success(self, mock_storage):
        """Test listing jobs successfully."""
        mock_job_data = [
            {"uuid": "uuid1", "chat_id": 123, "owner": 456, "hour": 10, "minute": 0, "command": "cmd1"},
            {"uuid": "uuid2", "chat_id": 123, "owner": 456, "hour": 11, "minute": 30, "command": "cmd2"},
        ]
        mock_storage.list_jobs.return_value = mock_job_data

        result_jobs = list_job("/listcron", 123, 456)

        self.assertEqual(len(result_jobs), 2)
        self.assertIsInstance(result_jobs[0], Job)
        self.assertIsInstance(result_jobs[1], Job)
        self.assertEqual(result_jobs[0].uuid, "uuid1")
        self.assertEqual(result_jobs[1].command, "cmd2")
        mock_storage.list_jobs.assert_called_once_with(456)

    def test_list_job_no_jobs(self, mock_storage):
        """Test listing jobs when the owner has none."""
        mock_storage.list_jobs.return_value = []
        result_jobs = list_job("/listcron", 123, 789)
        self.assertEqual(len(result_jobs), 0)
        mock_storage.list_jobs.assert_called_once_with(789)

    @patch('datetime.datetime')
    def test_run_cron_dispatch(self, mock_datetime, mock_storage):
        """Test run_cron dispatches due jobs."""
        # Mock time
        mock_now = MagicMock()
        mock_now.hour = 14
        mock_now.minute = 30
        mock_datetime.now.return_value = mock_now
        mock_datetime.UTC = datetime.UTC # Ensure UTC is available

        # Mock storage response
        mock_due_jobs_data = [
            {"uuid": "uuid1", "chat_id": 100, "owner": 200, "hour": 14, "minute": 30, "command": "do_task_1"},
            {"uuid": "uuid2", "chat_id": 101, "owner": 201, "hour": 14, "minute": 30, "command": "do_task_2"},
        ]
        mock_storage.get_due_jobs.return_value = mock_due_jobs_data

        # Mock dispatch function
        mock_dispatch = MagicMock()

        # Run cron
        run_cron(mock_dispatch)

        # Assertions
        mock_storage.get_due_jobs.assert_called_once_with(14, 30)
        self.assertEqual(mock_dispatch.call_count, 2)
        mock_dispatch.assert_has_calls([
            call("do_task_1", 100, 200),
            call("do_task_2", 101, 201),
        ], any_order=True) # Order isn't guaranteed

    @patch('datetime.datetime')
    def test_run_cron_no_due_jobs(self, mock_datetime, mock_storage):
        """Test run_cron when no jobs are due."""
        mock_now = MagicMock()
        mock_now.hour = 15
        mock_now.minute = 00
        mock_datetime.now.return_value = mock_now
        mock_datetime.UTC = datetime.UTC

        mock_storage.get_due_jobs.return_value = []
        mock_dispatch = MagicMock()

        run_cron(mock_dispatch)

        mock_storage.get_due_jobs.assert_called_once_with(15, 00)
        mock_dispatch.assert_not_called()

    @patch('datetime.datetime')
    def test_run_cron_skips_management_commands(self, mock_datetime, mock_storage):
        """Test run_cron skips jobs whose command is a management command."""
        mock_now = MagicMock()
        mock_now.hour = 16
        mock_now.minute = 00
        mock_datetime.now.return_value = mock_now
        mock_datetime.UTC = datetime.UTC

        mock_due_jobs_data = [
            {"uuid": "uuid1", "chat_id": 100, "owner": 200, "hour": 16, "minute": 0, "command": "/cron 17:00 other_task"},
            {"uuid": "uuid2", "chat_id": 101, "owner": 201, "hour": 16, "minute": 0, "command": "actual_task"},
            {"uuid": "uuid3", "chat_id": 102, "owner": 202, "hour": 16, "minute": 0, "command": "/delcron some_uuid"},
            {"uuid": "uuid4", "chat_id": 103, "owner": 203, "hour": 16, "minute": 0, "command": " listcron"}, # Space before command
        ]
        mock_storage.get_due_jobs.return_value = mock_due_jobs_data
        mock_dispatch = MagicMock()

        run_cron(mock_dispatch)

        mock_storage.get_due_jobs.assert_called_once_with(16, 00)
        # Only 'actual_task' should be dispatched
        mock_dispatch.assert_called_once_with("actual_task", 101, 201)

    @patch('datetime.datetime')
    def test_run_cron_handles_empty_command(self, mock_datetime, mock_storage):
        """Test run_cron handles jobs with empty commands gracefully."""
        mock_now = MagicMock()
        mock_now.hour = 17
        mock_now.minute = 00
        mock_datetime.now.return_value = mock_now
        mock_datetime.UTC = datetime.UTC

        mock_due_jobs_data = [
            {"uuid": "uuid1", "chat_id": 100, "owner": 200, "hour": 17, "minute": 0, "command": ""},
            {"uuid": "uuid2", "chat_id": 101, "owner": 201, "hour": 17, "minute": 0, "command": "  "}, # Whitespace only
        ]
        mock_storage.get_due_jobs.return_value = mock_due_jobs_data
        mock_dispatch = MagicMock()

        run_cron(mock_dispatch) # Should not raise an error

        mock_storage.get_due_jobs.assert_called_once_with(17, 00)
        mock_dispatch.assert_not_called() # No valid commands to dispatch


if __name__ == "__main__":
    # Ensure config.yaml exists for module loading, even if mocked later
    # This is a bit of a workaround for the top-level config load in cronjob.py
    if not os.path.exists("config.yaml"):
        with open("config.yaml", "w") as f:
            yaml.dump({"storage": {"backend": "sql", "sql": {"database_file": "dummy.db"}, "json": {"file_path": "dummy.json"}}}, f)

    unittest.main()
