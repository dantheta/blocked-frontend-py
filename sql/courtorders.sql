
create table court_judgments(
    id serial primary key,
	name varchar,
	date date,
	judgment_url varchar,
	url varchar,
    citation varchar,
    case_number varchar,
    restriction_type varchar,
    instruction_type varchar,
    jurisdiction varchar,
    power_id int,
    court_authority varchar,
    injunction_obtained_by varchar,
    injunction_obtained_by_url varchar,
    injunction_represented_by varchar,
    injunction_instructs varchar,
    other_docs text,
    sites_description text,
    
	created timestamptz,
	last_updated timestamptz
);

create unique index court_judgment_name on court_judgments(name);

create table court_powers(
    id serial primary key,
    name varchar unique,
    legislation varchar,

    created timestamptz,
    last_updated timestamptz
);

create table court_orders(
    id serial primary key,
    judgment_id int not null,
    network_name varchar,
    date date,
    expiry_date date,
    url varchar,
    created timestamptz,
    last_updated timestamptz
);

create unique index on court_orders(network_name, judgment_id);
alter table court_orders add foreign key (judgment_id) references court_judgments(id) on delete cascade;

create table court_judgment_urls(
    id serial primary key not null,
    judgment_id int null,
    url varchar not null,
    group_id int null,
    created timestamptz,
    last_updated timestamptz
);

create unique index on court_judgment_urls(judgment_id, url);
alter table court_judgment_urls add foreign key (judgment_id) references court_judgments(id) on delete cascade;


create table court_judgment_url_groups (
    id serial primary key,
    judgment_id int null,
    name varchar not null,
    created timestamptz,
    last_updated timestamptz
);

create unique index on court_judgment_url_groups(judgment_id, name);
alter table court_judgment_url_groups add foreign key (judgment_id) references court_judgments(id) on delete cascade;
alter table court_judgment_urls add foreign key (group_id) references court_judgment_url_groups(id) on delete set null;

insert into court_powers(name, legislation) values
('Copyright, Designs and Patents Act, Section 97A','http://www.legislation.gov.uk/ukpga/1988/48/section/97A'),
 ('Senior Courts Act 1981, Section 37 (1)','http://www.legislation.gov.uk/ukpga/1981/54/section/37'),
 ('Digital Economy Act 2017, section 23 (1)', 'http://www.legislation.gov.uk/ukpga/2017/30/section/23');
 
create table court_judgment_url_flags(
    id serial primary key,
    judgment_url_id int NULL unique,
    urlid int null unique,
    reason varchar not null,
    abusetype varchar,
    date_observed date, 
    description text,
    created timestamptz,
    last_updated timestamptz,
    check (NOT ((judgment_url_id is null AND urlid is null) OR (judgment_url_id is null AND urlid is null)))
);

alter table court_judgment_url_flags add foreign key (judgment_url_id) references court_judgment_urls(id) on delete cascade;

create table court_judgment_url_flag_history (like court_judgment_url_flags);
alter table court_judgment_url_flag_history add flag_id int not null;
create sequence court_judgment_url_flag_history_id_seq ;
alter table court_judgment_url_flag_history alter id set default nextval('court_judgment_url_flag_history_id_seq');
alter table court_judgment_url_flag_history add foreign key (judgment_url_id) references court_judgment_urls(id) on delete cascade;

create or replace function court_judgment_url_flag_upd_del() returns trigger AS $$
BEGIN
insert into court_judgment_url_flag_history(flag_id, judgment_url_id, urlid, reason, abusetype, date_observed, description, created, last_updated)
  select id, judgment_url_id, urlid, reason, abusetype, date_observed, description, created, last_updated 
  from court_judgment_url_flags where id = OLD.id;
  if TG_OP = 'UPDATE'
  then
    return NEW;
  else
    return OLD;
  end if;
END;
$$ language plpgsql;

create trigger court_judgment_url_flags_trig_upd
before update on court_judgment_url_flags 
for each row execute procedure court_judgment_url_flag_upd_del();

create trigger court_judgment_url_flags_trig_del 
before delete on court_judgment_url_flags 
for each row execute procedure court_judgment_url_flag_upd_del();

