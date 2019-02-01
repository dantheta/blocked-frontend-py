
create type enum_test_status as enum(
    'NEW',
    'RUNNING',
    'WAITING',
    'PAUSED',
    'COMPLETE',
    'ERROR',
    'CANCELLED'    
);

CREATE TABLE tests.test_cases (
    id serial primary key,
    name varchar not null,
    description varchar,
    created timestamptz not null,
    last_updated timestamptz not null,

    status enum_test_status default 'NEW',
    tags varchar[],
    filter varchar,
    sent int default 0,
    total int default 0,
    received int default 0,
    isps varchar[],
    check_interval interval default '5 min',
    last_check timestamptz,
    repeat_interval interval,
    last_run timestamptz,
    batch_size int default 250,
    last_id int default 0,
    status_message varchar null,
    vhost varchar(16) not null default '/'
);

CREATE TABLE tests.queue_status (
	queue_name varchar primary key,
	message_count int default 0,
	last_updated timestamptz
);
