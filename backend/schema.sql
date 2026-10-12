CREATE TABLE IF NOT EXISTS users (
  id uuid PRIMARY KEY,
  display_name text NOT NULL DEFAULT 'Local researcher',
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS sessions (
  id uuid PRIMARY KEY,
  user_id uuid NOT NULL REFERENCES users(id),
  title text NOT NULL DEFAULT 'New conversation',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS messages (
  id uuid PRIMARY KEY,
  session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('user','assistant')),
  content text NOT NULL,
  sources jsonb NOT NULL DEFAULT '[]',
  metadata jsonb NOT NULL DEFAULT '{}',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS messages_session ON messages(session_id,created_at);
CREATE TABLE IF NOT EXISTS artifacts (
  id uuid PRIMARY KEY,
  session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  message_id uuid NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
  title text NOT NULL,
  kind text NOT NULL CHECK (kind IN ('markdown','html')),
  content text NOT NULL,
  word_count int NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS episodes (
  id text PRIMARY KEY,
  title text NOT NULL,
  guest text NOT NULL,
  source_url text NOT NULL,
  video_url text,
  published text,
  content_hash text NOT NULL,
  source_revision text NOT NULL,
  indexed_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS chunks (
  id text PRIMARY KEY,
  episode_id text NOT NULL REFERENCES episodes(id) ON DELETE CASCADE,
  ordinal int NOT NULL,
  text text NOT NULL,
  timestamp text,
  search tsvector NOT NULL
);
CREATE INDEX IF NOT EXISTS chunks_search ON chunks USING gin(search);
CREATE INDEX IF NOT EXISTS chunks_episode ON chunks(episode_id);
CREATE TABLE IF NOT EXISTS jobs (
  id uuid PRIMARY KEY,
  session_id uuid NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
  status text NOT NULL DEFAULT 'queued',
  phase text NOT NULL DEFAULT 'Waiting for the selected model',
  request jsonb NOT NULL,
  message_id uuid REFERENCES messages(id),
  error_code text,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS jobs_one_active_session ON jobs(session_id)
WHERE status IN ('queued','running');


ALTER TABLE messages ADD COLUMN IF NOT EXISTS saved boolean NOT NULL DEFAULT false;

ALTER TABLE jobs ALTER COLUMN phase SET DEFAULT 'Waiting for the selected model';
