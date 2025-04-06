import datetime
import uuid
import sqlite3
import json
import re
import yaml
from dataclasses import dataclass
from abc import ABC, abstractmethod

# Load config
with open("config.yaml") as f:
    config = yaml.safe_load(f)

DB_FILE = config["storage"]["sql"]["database_file"]
JSON_FILE = config["storage"]["json"]["file_path"]
MAX_JOBS_PER_OWNER = 10


class MaxJobsReachedError(Exception):
    """Custom exception for when an owner reaches the maximum job limit."""

    pass


class Storage(ABC):
    """Abstract base class for storage backends."""

    @abstractmethod
    def init_db(self):
        """Initialize the storage backend."""
        pass

    @abstractmethod
    def add_job(
        self,
        job_uuid: str,
        chat_id: int,
        owner: int,
        hour: int,
        minute: int,
        command: str,
    ) -> None:
        """Add a new job to storage."""
        pass

    @abstractmethod
    def del_job(self, job_uuid: str, owner: int) -> bool:
        """Delete a job from storage."""
        pass

    @abstractmethod
    def list_jobs(self, owner: int) -> list:
        """List all jobs for an owner."""
        pass

    @abstractmethod
    def get_due_jobs(self, hour: int, minute: int) -> list:
        """Get jobs due at the specified time."""
        pass


class SQLStorage(Storage):
    """SQLite storage implementation."""

    def __init__(self, db_file: str):
        self.db_file = db_file
        self.init_db()

    def init_db(self):
        """Initialize the SQLite database."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                uuid TEXT PRIMARY KEY,
                chat_id INTEGER,
                owner INTEGER,
                hour INTEGER,
                minute INTEGER,
                command TEXT
            )
            """)

    def add_job(
        self,
        job_uuid: str,
        chat_id: int,
        owner: int,
        hour: int,
        minute: int,
        command: str,
    ) -> None:
        """Add a new job to SQL storage."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM jobs WHERE owner = ?", (owner,))
            if cursor.fetchone()[0] >= MAX_JOBS_PER_OWNER:
                raise MaxJobsReachedError(
                    f"Owner {owner} has reached the maximum limit of {MAX_JOBS_PER_OWNER} jobs."
                )

            cursor.execute(
                "INSERT INTO jobs (uuid, chat_id, owner, hour, minute, command) VALUES (?, ?, ?, ?, ?, ?)",
                (job_uuid, chat_id, owner, hour, minute, command),
            )

    def del_job(self, job_uuid: str, owner: int) -> bool:
        """Delete a job from SQL storage."""
        with sqlite3.connect(self.db_file) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM jobs WHERE uuid = ? AND owner = ?", (job_uuid, owner)
            )
            return cursor.rowcount > 0

    def list_jobs(self, owner: int) -> list:
        """List all jobs for an owner from SQL storage."""
        with sqlite3.connect(self.db_file) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT uuid, chat_id, owner, hour, minute, command FROM jobs WHERE owner = ?",
                (owner,),
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_due_jobs(self, hour: int, minute: int) -> list:
        """Get jobs due at the specified time from SQL storage."""
        with sqlite3.connect(self.db_file) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute(
                "SELECT uuid, chat_id, owner, hour, minute, command FROM jobs WHERE hour = ? AND minute = ?",
                (hour, minute),
            )
            return [dict(row) for row in cursor.fetchall()]


class JSONStorage(Storage):
    """JSON file storage implementation."""

    def __init__(self, file_path: str):
        self.file_path = file_path
        self.init_db()

    def init_db(self):
        """Initialize the JSON storage file."""
        try:
            with open(self.file_path, "r") as f:
                json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            with open(self.file_path, "w") as f:
                json.dump([], f)

    def add_job(
        self,
        job_uuid: str,
        chat_id: int,
        owner: int,
        hour: int,
        minute: int,
        command: str,
    ) -> None:
        """Add a new job to JSON storage."""
        with open(self.file_path, "r+") as f:
            jobs = json.load(f)
            if len([j for j in jobs if j["owner"] == owner]) >= MAX_JOBS_PER_OWNER:
                raise MaxJobsReachedError(
                    f"Owner {owner} has reached the maximum limit of {MAX_JOBS_PER_OWNER} jobs."
                )

            jobs.append(
                {
                    "uuid": job_uuid,
                    "chat_id": chat_id,
                    "owner": owner,
                    "hour": hour,
                    "minute": minute,
                    "command": command,
                }
            )
            f.seek(0)
            json.dump(jobs, f, indent=2)
            f.truncate()

    def del_job(self, job_uuid: str, owner: int) -> bool:
        """Delete a job from JSON storage."""
        with open(self.file_path, "r+") as f:
            jobs = json.load(f)
            initial_count = len(jobs)
            jobs = [
                j for j in jobs if not (j["uuid"] == job_uuid and j["owner"] == owner)
            ]
            if len(jobs) < initial_count:
                f.seek(0)
                json.dump(jobs, f, indent=2)
                f.truncate()
                return True
            return False

    def list_jobs(self, owner: int) -> list:
        """List all jobs for an owner from JSON storage."""
        with open(self.file_path, "r") as f:
            jobs = json.load(f)
            return [j for j in jobs if j["owner"] == owner]

    def get_due_jobs(self, hour: int, minute: int) -> list:
        """Get jobs due at the specified time from JSON storage."""
        with open(self.file_path, "r") as f:
            jobs = json.load(f)
            return [j for j in jobs if j["hour"] == hour and j["minute"] == minute]


# Initialize storage based on config
storage = (
    SQLStorage(DB_FILE)
    if config["storage"]["backend"] == "sql"
    else JSONStorage(JSON_FILE)
)


@dataclass
class Job:
    uuid: str
    chat_id: str
    owner: str
    hour: int
    minute: int
    command: str


def parse_job(text: str) -> tuple[str, int, int]:
    """Parses job text like '/cron HH:MM command' using regex."""
    # Regex to capture HH:MM and the command part
    # Allows flexible spacing around time and command
    match = re.match(r"/\w+\s+(\d{1,2})\s*:\s*(\d{1,2})\s+(.*)", text)
    if not match:
        raise ValueError("Invalid job format. Expected '/cron HH:MM command'")

    hour_str, minute_str, command = match.groups()
    hour = int(hour_str)
    minute = int(minute_str)

    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("Invalid time format. Hour must be 0-23, Minute must be 0-59.")

    return command.strip(), hour, minute


def add_job(text: str, chat_id: int, owner: int) -> str:
    """Adds a new cron job to storage."""
    command, hour, minute = parse_job(text)
    job_uuid = str(uuid.uuid4())
    storage.add_job(job_uuid, chat_id, owner, hour, minute, command)
    return job_uuid


def del_job(text: str, chat_id: int, owner: int) -> bool:
    """Deletes a cron job by UUID, ensuring ownership."""
    parts = text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1]:
        raise ValueError("Invalid delete format. Expected '/delcron UUID'")
    job_uuid = parts[1].strip()
    return storage.del_job(job_uuid, owner)


def list_job(text: str, chat_id: int, owner: int) -> list[Job]:
    """Lists all cron jobs for a specific owner as Job objects."""
    jobs_data = storage.list_jobs(owner)
    return [Job(**job) for job in jobs_data]


def run_cron(dispatch_func):
    """Fetches and runs due cron jobs."""
    now = datetime.datetime.now(datetime.UTC)
    current_hour = now.hour
    current_minute = now.minute

    jobs_data = storage.get_due_jobs(current_hour, current_minute)
    jobs_to_run = [Job(**job) for job in jobs_data]

    for job in jobs_to_run:
        # Avoid running cron management commands themselves if scheduled
        # Check if the first part of the command (e.g., '/cron') matches known management commands
        try:
            first_command_part = job.command.split()[0].lstrip("/")
            # List of commands that should not be executed by the cron runner itself
            management_commands = {"cron", "addcron", "delcron", "listcron"}
            if first_command_part in management_commands:
                continue
        except IndexError:
            # Handle cases where command might be empty or malformed
            continue

        dispatch_func(job.command, job.chat_id, job.owner)


if __name__ == "__main__":
    run_cron(print)
