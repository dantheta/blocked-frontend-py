
create type enum_test_status as enum(
    'NEW',
    'RUNNING',
    'PAUSED',
    'ERROR',
    'CANCELLED'
);

CREATE TABLE test_cases (
    id serial primary key,
    name varchar not null,
    description varchar,
    created timestamptz not null,
    last_updated timestamptz not null,

    status enum_test_status default 'NEW',
    tag varchar,
    filter varchar,
    sent int default 0,
    total int default 0,
    received int default 0,
    routing_key varchar,
    isps varchar[],
    check_interval interval,
    last_check timestamptz,
    repeat_interval interval,
    last_run timestamptz,
    batch_size int default 250
);