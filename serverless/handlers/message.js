import { dispatch } from 'lib/dispatcher';
import { runCron } from 'lib/cron';

export default async function (message, ctx) {
  if (message && message.text) {
    const text = message.text.trim();
    const chatId = message.chat.id;
    const fromId = message.from.id;

    await dispatch(text, chatId, fromId);
  }

  // Execute due cron jobs
  await runCron(dispatch);
}
