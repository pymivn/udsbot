import datetime
import uuid
import sqlite3
from dataclasses import dataclass

DB_FILE = "cronjobs.db"
MAX_JOBS_PER_OWNER = 10


@dataclass
class Job:
    uuid: str
    chat_id: str
    owner: str
    hour: int
    minute: int
    command: str


def init_db():
    """Initialize the SQLite database and create the jobs table if it doesn't exist."""
    conn = sqlite3.connect(DB_FILE)
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
    conn.commit()
    conn.close()


def parse_job(text: str) -> tuple[str, int, int]:
    # 13:45 jo
    _cron, hm, cmd = text.split()
    hour, minute = hm.split(":")
    return cmd, int(hour), int(minute)


def add_job(text: str, chat_id: int, owner: int) -> str:
    command, hour, minute = parse_job(text)

    # Initialize the database if it doesn't exist
    init_db()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Count jobs by owner
    cursor.execute("SELECT COUNT(*) FROM jobs WHERE owner = ?", (owner,))
    count_jobs_by_owner = cursor.fetchone()[0]

    if count_jobs_by_owner >= MAX_JOBS_PER_OWNER:
        conn.close()
        raise Exception(f"IGNORE cron add as {owner} has reached max jobs")

    job_uuid = str(uuid.uuid4())

    # Insert new job
    cursor.execute(
        "INSERT INTO jobs (uuid, chat_id, owner, hour, minute, command) VALUES (?, ?, ?, ?, ?, ?)",
        (job_uuid, chat_id, owner, hour, minute, command),
    )

    conn.commit()
    conn.close()

    return job_uuid


def del_job(text: str, chat_id: int, owner: int) -> bool:
    prefix, job_uuid = text.split()

    # Initialize the database if it doesn't exist
    init_db()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Delete job if it matches the UUID and owner
    cursor.execute("DELETE FROM jobs WHERE uuid = ? AND owner = ?", (job_uuid, owner))

    conn.commit()
    conn.close()

    return True


def list_job(text: str, chat_id: int, owner: int) -> list[dict]:
    # Initialize the database if it doesn't exist
    init_db()

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row  # Enable row factory to access columns by name
    cursor = conn.cursor()

    # Get all jobs for the owner
    cursor.execute(
        "SELECT uuid, chat_id, owner, hour, minute, command FROM jobs WHERE owner = ?",
        (owner,),
    )
    rows = cursor.fetchall()

    # Convert to list of dictionaries
    jobs = [dict(row) for row in rows]

    conn.close()

    return jobs


def run_cron(dispatch_func):
    # Initialize the database if it doesn't exist
    init_db()

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    # Get all jobs
    cursor.execute("SELECT uuid, chat_id, owner, hour, minute, command FROM jobs")
    jobs_data = cursor.fetchall()

    conn.close()

    # Convert to Job objects
    jobs = [
        Job(uuid=j[0], chat_id=j[1], owner=j[2], hour=j[3], minute=j[4], command=j[5])
        for j in jobs_data
    ]

    now = datetime.datetime.now(datetime.UTC)

    for job in jobs:
        if job.command.split()[0].lstrip("/") == "cron":
            continue

        if (now.hour, now.minute) == (job.hour, job.minute):
            dispatch_func(job.command, job.chat_id, job.owner)


if __name__ == "__main__":
    run_cron(print)
