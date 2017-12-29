
create table court_judgments(
    id serial primary key,
	name varchar,
	date date,
	url varchar,
    citation varchar,
    case_number varchar,
    restriction_type varchar,
    instruction_type varchar,
    jurisdiction varchar,
    power_id int,
    court_authority varchar,
    injunction_obtained_by varchar,
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

insert into court_powers(name, legislation) values
('Copyright, Designs and Patents Act, Section 97A','http://www.legislation.gov.uk/ukpga/1988/48/section/97A'),
 ('Senior Courts Act 1981, Section 37 (1)','http://www.legislation.gov.uk/ukpga/1981/54/section/37'),
 ('Digital Economy Act 2017, section 23 (1)', 'http://www.legislation.gov.uk/ukpga/2017/30/section/23');