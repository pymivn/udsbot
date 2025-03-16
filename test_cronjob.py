import unittest
import json
import os
import datetime
from unittest.mock import patch, MagicMock
import uuid

# Import your module - adjust the import statement as needed
import sys

sys.path.append(".")
from cronjob import parse_job, add_job, del_job, list_job, run_cron, CRON_JOBS_FILE


class TestCronJobFunctions(unittest.TestCase):
    def setUp(self):
        # Create a temporary file for testing
        self.test_file = "test_cronjobs.json"
        self.original_cron_jobs_file = CRON_JOBS_FILE
        # Use test file instead of real one
        globals()["CRON_JOBS_FILE"] = self.test_file

    def tearDown(self):
        # Clean up after each test
        globals()["CRON_JOBS_FILE"] = self.original_cron_jobs_file
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

    # Tests for parse_job function
    def test_parse_job_valid_input(self):
        command, hour, minute = parse_job("/cron 13:45 btc")
        self.assertEqual(command, "btc")
        self.assertEqual(hour, 13)
        self.assertEqual(minute, 45)

    def test_parse_job_with_different_time(self):
        command, hour, minute = parse_job("/cron 08:05 hi")
        self.assertEqual(command, "hi")
        self.assertEqual(hour, 8)
        self.assertEqual(minute, 5)

    def test_parse_job_with_complex_command(self):
        command, hour, minute = parse_job("/cron 23:59 /send_report to all users")
        self.assertEqual(command, "/send_report to all users")
        self.assertEqual(hour, 23)
        self.assertEqual(minute, 59)

    # Tests for add_job function
    @patch("uuid.uuid4")
    def test_add_job_new_file(self, mock_uuid):
        mock_uuid.return_value = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        job_uuid = add_job("cron 10:30 /echo test", 123456, 987654)

        self.assertEqual(job_uuid, "12345678-1234-1234-1234-123456789abc")

        # Verify the job was added correctly
        with open(self.test_file, "r") as f:
            jobs = json.load(f)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["uuid"], job_uuid)
        self.assertEqual(jobs[0]["chat_id"], 123456)
        self.assertEqual(jobs[0]["owner"], 987654)
        self.assertEqual(jobs[0]["hour"], 10)
        self.assertEqual(jobs[0]["minute"], 30)
        self.assertEqual(jobs[0]["command"], "/echo test")

    @patch("uuid.uuid4")
    def test_add_job_existing_file(self, mock_uuid):
        initial_jobs = [
            {
                "uuid": "existing-uuid-1",
                "chat_id": 123456,
                "owner": 987654,
                "hour": 9,
                "minute": 15,
                "command": "/echo previous",
            }
        ]

        with open(self.test_file, "w") as f:
            json.dump(initial_jobs, f)

        mock_uuid.return_value = uuid.UUID("12345678-1234-1234-1234-123456789abc")
        job_uuid = add_job("cron 10:30 /echo test", 123456, 987654)

        # Verify both jobs are in the file
        with open(self.test_file, "r") as f:
            jobs = json.load(f)

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[1]["uuid"], job_uuid)
        self.assertEqual(jobs[0]["uuid"], "existing-uuid-1")

    def test_add_job_max_limit(self):
        initial_jobs = []
        for i in range(10):  # MAX_JOBS_PER_OWNER is 10
            initial_jobs.append(
                {
                    "uuid": f"existing-uuid-{i}",
                    "chat_id": 123456,
                    "owner": 987654,
                    "hour": 9,
                    "minute": 15,
                    "command": f"/echo previous {i}",
                }
            )

        with open(self.test_file, "w") as f:
            json.dump(initial_jobs, f)

        # This should raise an exception
        with self.assertRaises(Exception) as context:
            add_job("cron 10:30 /echo test", 123456, 987654)

        self.assertTrue(
            "IGNORE cron add as 987654 has reached max jobs" in str(context.exception)
        )

    # Tests for del_job function
    def test_del_job_existing(self):
        initial_jobs = [
            {
                "uuid": "job-to-delete",
                "chat_id": 123456,
                "owner": 987654,
                "hour": 9,
                "minute": 15,
                "command": "/echo delete me",
            },
            {
                "uuid": "job-to-keep",
                "chat_id": 123456,
                "owner": 987654,
                "hour": 10,
                "minute": 30,
                "command": "/echo keep me",
            },
        ]

        with open(self.test_file, "w") as f:
            json.dump(initial_jobs, f)

        result = del_job("del job-to-delete", 123456, 987654)

        self.assertTrue(result)

        # Verify only one job remains
        with open(self.test_file, "r") as f:
            jobs = json.load(f)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["uuid"], "job-to-keep")

    def test_del_job_nonexistent(self):
        initial_jobs = [
            {
                "uuid": "existing-job",
                "chat_id": 123456,
                "owner": 987654,
                "hour": 9,
                "minute": 15,
                "command": "/echo existing",
            }
        ]

        with open(self.test_file, "w") as f:
            json.dump(initial_jobs, f)

        result = del_job("del non-existent-job", 123456, 987654)

        self.assertTrue(result)  # Function returns True regardless

        # Verify original job still exists
        with open(self.test_file, "r") as f:
            jobs = json.load(f)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["uuid"], "existing-job")

    def test_del_job_wrong_owner(self):
        initial_jobs = [
            {
                "uuid": "job-to-delete",
                "chat_id": 123456,
                "owner": 987654,
                "hour": 9,
                "minute": 15,
                "command": "/echo delete me",
            }
        ]

        with open(self.test_file, "w") as f:
            json.dump(initial_jobs, f)

        result = del_job("del job-to-delete", 123456, 111111)  # Different owner

        self.assertTrue(result)  # Function returns True regardless

        # Verify job still exists (not deleted)
        with open(self.test_file, "r") as f:
            jobs = json.load(f)

        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["uuid"], "job-to-delete")

    # Tests for list_job function
    def test_list_job_with_jobs(self):
        initial_jobs = [
            {
                "uuid": "job-1",
                "chat_id": 123456,
                "owner": 987654,
                "hour": 9,
                "minute": 15,
                "command": "/echo job 1",
            },
            {
                "uuid": "job-2",
                "chat_id": 123456,
                "owner": 987654,
                "hour": 10,
                "minute": 30,
                "command": "/echo job 2",
            },
            {
                "uuid": "job-3",
                "chat_id": 123456,
                "owner": 111111,  # Different owner
                "hour": 11,
                "minute": 45,
                "command": "/echo job 3",
            },
        ]

        with open(self.test_file, "w") as f:
            json.dump(initial_jobs, f)

        jobs = list_job("list", 123456, 987654)

        self.assertEqual(len(jobs), 2)
        self.assertEqual(jobs[0]["uuid"], "job-1")
        self.assertEqual(jobs[1]["uuid"], "job-2")

    def test_list_job_no_jobs(self):
        initial_jobs = [
            {
                "uuid": "job-1",
                "chat_id": 123456,
                "owner": 111111,  # Different owner
                "hour": 9,
                "minute": 15,
                "command": "/echo job 1",
            }
        ]

        with open(self.test_file, "w") as f:
            json.dump(initial_jobs, f)

        jobs = list_job("list", 123456, 987654)

        self.assertEqual(len(jobs), 0)

    def test_list_job_empty_file(self):
        # Test listing jobs with an empty file
        if os.path.exists(self.test_file):
            os.remove(self.test_file)

        jobs = list_job("list", 123456, 987654)
        self.assertEqual(len(jobs), 0)

    # Tests for run_cron function
    @patch("datetime.datetime")
    def test_run_cron_matching_time(self, mock_datetime):
        mock_datetime.utcnow.return_value = datetime.datetime(2023, 1, 1, 10, 30)

        initial_jobs = [
            {
                "uuid": "job-1",
                "chat_id": 123456,
                "owner": 987654,
                "hour": 10,
                "minute": 30,  # Matches current time
                "command": "/echo run me",
            }
        ]

        with open(self.test_file, "w") as f:
            json.dump(initial_jobs, f)

        dispatch_mock = MagicMock()
        run_cron(dispatch_mock)

        # Verify dispatch_func was called with correct parameters
        dispatch_mock.assert_called_once_with("/echo run me", 123456, 987654)

    @patch("datetime.datetime")
    def test_run_cron_different_time(self, mock_datetime):
        mock_datetime.utcnow.return_value = datetime.datetime(2023, 1, 1, 10, 30)

        initial_jobs = [
            {
                "uuid": "job-1",
                "chat_id": 123456,
                "owner": 987654,
                "hour": 9,
                "minute": 15,  # Different time
                "command": "/echo run me",
            }
        ]

        with open(self.test_file, "w") as f:
            json.dump(initial_jobs, f)

        dispatch_mock = MagicMock()
        run_cron(dispatch_mock)

        # Verify dispatch_func was not called
        dispatch_mock.assert_not_called()

    @patch("datetime.datetime")
    def test_run_cron_skip_cron_command(self, mock_datetime):
        mock_datetime.utcnow.return_value = datetime.datetime(2023, 1, 1, 10, 30)

        initial_jobs = [
            {
                "uuid": "job-1",
                "chat_id": 123456,
                "owner": 987654,
                "hour": 10,
                "minute": 30,  # Matches current time
                "command": "/cron add another_job",
            }
        ]

        with open(self.test_file, "w") as f:
            json.dump(initial_jobs, f)

        dispatch_mock = MagicMock()
        run_cron(dispatch_mock)

        # Verify dispatch_func was not called (skipped because command starts with cron)
        dispatch_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
