
CREATE TABLE savedlists(
    id serial primary key not null,
    username varchar not null,
    created timestamptz not null,
    last_updated timestamptz null
    );

CREATE TABLE items (
    id serial primary key not null,
    list_id int not null,
    url varchar not null,
    title varchar not null,
    created timestamptz not null,
    last_updated timestamptz null
    );

ALTER TABLE items ADD foreign key (list_id) references savedlists(id) ON DELETE CASCADE;

