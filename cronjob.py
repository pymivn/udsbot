import os
import json
import datetime
import uuid
from dataclasses import dataclass

CRON_JOBS_FILE = "cronjobs.json"
OWNERS_WHITELIST: list[int] = [
    int(i) for i in os.environ.get("OWNERS_WHITELIST", "").replace(",", " ").split()
]
MAX_JOBS_PER_OWNER = 10


@dataclass
class Job:
    chat_id: str
    owner: str
    hour: int
    minute: int
    command: str


def parse_job(text: str) -> (str, int, int):
    # 13:45 jo
    _cron, hm, cmd = text.split()
    hour, minute = hm.split(":")
    return cmd, int(hour), int(minute)


def add_job(text: str, chat_id: int, owner: int) -> str:
    command, hour, minute = parse_job(text)

    try:
        with open(CRON_JOBS_FILE, "r") as f:
            jobs = json.load(f)
    except FileNotFoundError:
        jobs = []

    count_jobs_by_owner = len([job for job in jobs if job["owner"] == owner])
    if count_jobs_by_owner >= MAX_JOBS_PER_OWNER:
        raise Exception(f"IGNORE cron add as {owner} has reached max jobs")

    job_uuid = uuid.uuid4()

    with open(CRON_JOBS_FILE, "w") as f:
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
        json.dump(jobs, f)
    return job_uuid


def del_job(text: str, chat_id: int, owner: int) -> bool:
    prefix, job_uuid = text.split()

    try:
        with open(CRON_JOBS_FILE, "r") as f:
            jobs = json.load(f)
    except FileNotFoundError:
        jobs = []
    with open(CRON_JOBS_FILE, "w") as f:
        jobs = [j for j in jobs if not (job_uuid == j["uuid"] and owner == j["owner"])]
        json.dump(jobs, f)
    return True


def list_job(text: str, chat_id: int, owner: int) -> list(dict):
    try:
        with open(CRON_JOBS_FILE, "r") as f:
            jobs = json.load(f)
    except FileNotFoundError:
        jobs = []
    return [j for j in jobs if owner == j["owner"]]


def add_uuid(text: str, chat_id: int, owner: int) -> int:
    try:
        with open(CRON_JOBS_FILE, "r") as f:
            jobs = json.load(f)
    except FileNotFoundError:
        jobs = []

    count = 0
    for job in jobs:
        if job.get("uuid", "") == "":
            job["uuid"] = uuid.uuid4()
            count += 1

    with open(CRON_JOBS_FILE, "w") as f:
        json.dump(jobs, f)
    return count


def run_cron(dispatch_func):
    try:
        with open(CRON_JOBS_FILE) as f:
            jobs = json.load(f)
    except FileNotFoundError:
        jobs = []

    now = datetime.datetime.utcnow()
    for j in jobs:
        job = Job(**j)
        if job.command.split()[0].lstrip("/") == "cron":
            continue
        if (now.hour, now.minute) == (job.hour, job.minute):
            dispatch_func(job.command, job.chat_id, job.owner)


if __name__ == "__main__":
    run_cron(print)
