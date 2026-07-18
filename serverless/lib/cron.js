import { db, eq, and } from 'sdk/db';
import { jobs } from 'schema';

const MAX_JOBS_PER_OWNER = 10;

export async function addJob(text, chatId, owner) {
  // Regex to capture HH:MM and the command part
  const match = text.match(/^\/\w+\s+(\d{1,2})\s*:\s*(\d{1,2})\s+(.*)$/);
  if (!match) {
    throw new Error("Invalid job format. Expected '/cron HH:MM command'");
  }

  const hour = parseInt(match[1], 10);
  const minute = parseInt(match[2], 10);
  const command = match[3].trim();

  if (hour < 0 || hour > 23 || minute < 0 || minute > 59) {
    throw new Error('Invalid time format. Hour must be 0-23, Minute must be 0-59.');
  }

  const count = await db.$count(jobs, eq(jobs.owner, owner));
  if (count >= MAX_JOBS_PER_OWNER) {
    throw new Error(`Owner has reached the maximum limit of ${MAX_JOBS_PER_OWNER} jobs.`);
  }

  const jobUuid = typeof crypto !== 'undefined' && crypto.randomUUID 
    ? crypto.randomUUID() 
    : Math.random().toString(36).slice(2) + '-' + Date.now().toString(36);

  await db.insert(jobs).values({
    uuid: jobUuid,
    chatId,
    owner,
    hour,
    minute,
    command,
    lastRun: null,
  }).run();

  return jobUuid;
}

export async function delJob(text, chatId, owner) {
  const parts = text.split(/\s+/);
  if (parts.length < 2 || !parts[1]) {
    throw new Error("Invalid delete format. Expected '/delcron UUID'");
  }
  const jobUuid = parts[1].trim();

  const res = await db.delete(jobs)
    .where(and(eq(jobs.uuid, jobUuid), eq(jobs.owner, owner)))
    .returning()
    .run();
  return res.length > 0;
}

export async function listJobs(text, chatId, owner) {
  return await db.select().from(jobs).where(eq(jobs.owner, owner)).all();
}

let lastCheckedMinute = -1;

export async function runCron(dispatchFunc) {
  const now = new Date();
  const currentHour = now.getUTCHours();
  const currentMinute = now.getUTCMinutes();

  if (currentMinute === lastCheckedMinute) {
    return;
  }
  lastCheckedMinute = currentMinute;

  const todayStr = now.toISOString().slice(0, 10); // YYYY-MM-DD

  const allJobs = await db.select().from(jobs).all();

  for (const job of allJobs) {
    let firstPart = '';
    try {
      firstPart = job.command.split(/\s+/)[0].replace(/^\//, '');
    } catch (e) {
      continue;
    }
    const managementCommands = ['cron', 'addcron', 'delcron', 'listcron'];
    if (managementCommands.includes(firstPart)) {
      continue;
    }

    const isPastScheduledTime = (currentHour > job.hour) || (currentHour === job.hour && currentMinute >= job.minute);
    const notRunToday = job.lastRun !== todayStr;

    if (isPastScheduledTime && notRunToday) {
      try {
        console.log(`Running scheduled job ${job.uuid} for chat ${job.chatId}: ${job.command}`);
        await dispatchFunc(job.command, job.chatId, job.owner);
      } catch (e) {
        console.error(`Error running job ${job.uuid}:`, e);
      }

      await db.update(jobs)
        .set({ lastRun: todayStr })
        .where(eq(jobs.uuid, job.uuid))
        .run();
    }
  }
}
