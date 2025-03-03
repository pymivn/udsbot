import os
import json
import datetime
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


def count_jobs_by_owner(owner: int) -> int:
    try:
        with open(CRON_JOBS_FILE, "r") as f:
            jobs = json.load(f)
    except FileNotFoundError:
        return 0
    return len([job for job in jobs if job["owner"] == owner])


def add_job(text: str, chat_id: int, owner: int) -> bool:
    if owner not in OWNERS_WHITELIST:
        raise Exception(f"IGNORE cron add as {owner} not in OWNERS_WHITELIST")

    if count_jobs_by_owner(owner) > MAX_JOBS_PER_OWNER:
        raise Exception(f"IGNORE cron add as {owner} has reached max jobs")

    command, hour, minute = parse_job(text)

    try:
        with open(CRON_JOBS_FILE, "r") as f:
            jobs = json.load(f)
    except FileNotFoundError:
        jobs = []

    with open(CRON_JOBS_FILE, "w") as f:
        jobs.append(
            {
                "chat_id": chat_id,
                "owner": owner,
                "hour": hour,
                "minute": minute,
                "command": command,
            }
        )
        json.dump(jobs, f)
    return True


def del_job(text: str, chat_id: int, owner: int) -> bool:
    del_job_chat_id = int(text.split()[1])

    try:
        with open(CRON_JOBS_FILE, "r") as f:
            jobs = json.load(f)
    except FileNotFoundError:
        jobs = []
    with open(CRON_JOBS_FILE, "w") as f:
        jobs = [
            j
            for j in jobs
            if not (
                chat_id and chat_id == j["del_job_chat_id"] and owner and owner == j["owner"]
            )
        ]
        json.dump(jobs, f)
    return True


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
