CREATE TABLE IF NOT EXISTS blacklist (
    user_id BIGINT UNIQUE PRIMARY KEY NOT NULL,
    mod_id BIGINT NOT NULL
);

CREATE TABLE IF NOT EXISTS guilds (
    guild_id BIGINT UNIQUE PRIMARY KEY NOT NULL,
    prefix VARCHAR(10),
    custom_dollar_sign VARCHAR(30)
);

CREATE TABLE IF NOT EXISTS snipes (
    channel_id BIGINT UNIQUE PRIMARY KEY NOT NULL,
    guild_id BIGINT NOT NULL,
    user_id BIGINT NOT NULL,
    message_id BIGINT NOT NULL,
    message VARCHAR(2000) NOT NULL,
    msg_type INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS past_igns (
    past_ign VARCHAR(32) Not NULL,
    uuid1 INTEGER NOT NULL,
    uuid2 INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS economy (
    user_id BIGINT PRIMARY KEY UNIQUE NOT NULL,
    money BIGINT NOT NULL DEFAULT (0),
    last_daily INTEGER,
    daily_streak INTEGER DEFAULT (0)
);
