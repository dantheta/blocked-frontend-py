
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
    judgment_id int not null,
    url varchar not null,
    group_id int,
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