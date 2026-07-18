import { table, integer, text } from 'sdk/db';

export const jobs = table('jobs', {
  uuid:    text('uuid').primaryKey(),
  chatId:  integer('chat_id').notNull(),
  owner:   integer('owner').notNull(),
  hour:    integer('hour').notNull(),
  minute:  integer('minute').notNull(),
  command: text('command').notNull(),
  lastRun: text('last_run'), // format: YYYY-MM-DD
});

export const cache = table('cache', {
  key:       text('key').primaryKey(),
  val:       text('val').notNull(),
  updatedAt: integer('updated_at').notNull(), // Unix timestamp in seconds
});
