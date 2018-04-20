
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
    created timestamptz not null,
    last_updated timestamptz not null
    );
