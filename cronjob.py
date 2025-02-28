import os
import json
import datetime
from dataclasses import dataclass

CRON_JOBS_FILE = "cronjobs.json"
OWNERS_WHITELIST: list[int] = [
    int(i) for i in os.environ.get("OWNERS_WHITELIST", "").replace(",", " ").split()
]


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


def add_job(text: str, chat_id: int, owner: int) -> bool:
    if owner not in OWNERS_WHITELIST:
        print(f"IGNORE cron add as {owner} not in OWNERS_WHITELIST")
        return False

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
