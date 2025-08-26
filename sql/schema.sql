
CREATE TABLE savedlists(
    id serial primary key not null,
    username varchar not null,
    name varchar not null,
    public bool default true,
    frontpage bool default false,
    created timestamptz not null,
    last_updated timestamptz null
    );

CREATE TABLE items (
    id serial primary key not null,
    list_id int not null,
    url varchar not null,
    title varchar not null,
    reported bool default false not null,
    blocked bool null,
    networks varchar[] null,
    created timestamptz not null,
    last_updated timestamptz null,
    last_checked timestamptz null
    );

ALTER TABLE items ADD foreign key (list_id) references savedlists(id) ON DELETE CASCADE;

CREATE UNIQUE INDEX savedlists_name ON savedlists(name);
CREATE UNIQUE INDEX items_listid_url ON items(list_id, url);

CREATE TYPE enum_user_level as enum(
'user',
'reviewer',
'moderator',
'admin'
);

CREATE TABLE users(
    id serial primary key,
    username varchar unique,
    email varchar unique,
    password varchar,
    user_type enum_user_level not null default 'user',
    enabled bool default true,
    created timestamptz not null,
    last_updated timestamptz not null
    );


CREATE TYPE enum_osacase_source AS ENUM (
    'user',
    'detected',
    'operator'
);
CREATE TYPE enum_osacase_block_type AS ENUM(
    'geoblock_osa',
    'geoblock_misc',
    'shutdown_osa'
);

CREATE TYPE enum_osacase_status AS ENUM(
    'duplicate',
    'rejected',
    'submitted',
    'confirmed',
    'relaunched'
);


CREATE TABLE osa_cases(
    id serial primary key,
    urlid int NOT NULL,
    contact_id int NULL,
    source enum_osacase_source NOT NULL,
    block_type enum_osacase_block_type,
    description text null,
    archive_url text,
    status enum_osacase_status DEFAULT 'submitted' NOT NULL,
    shutdown_date date null,

    relaunch_url varchar null,
    relaunch_date date null,
    
    reasons varchar[] default '{}',
    modifications varchar[] default '{}',
    comments text null,
    
    reviewed_userid int null,
    reviewed_timestamp timestamptz null,
    created timestamptz not null,
    last_updated timestamptz null
);

CREATE UNIQUE INDEX ON osa_cases(urlid) WHERE status >= 'submitted';

