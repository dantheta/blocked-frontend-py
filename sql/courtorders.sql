
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
    rightsholder_id int null,
    
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


create view active_copyright_blocks as
select urls.urlid, urls.url, uls.id as url_latest_status_id, regions, network_name, uls.first_blocked, uls.last_blocked from 
    urls 
    inner join url_latest_status uls on urls.urlid = uls.urlid
        and uls.status = 'blocked' and uls.blocktype = 'COPYRIGHT'
    inner join isps on isps.name = uls.network_name
    where urls.url ~* '^https?://[^/]+$' and urls.status = 'ok';

create or replace view active_court_blocks as 
      -- copyright blocks with or without judgments
      select cj.id as judgment_id, cj.name judgment_name, cj.date judgment_date, cj.url wiki_url, cj.judgment_url judgment_url, cj.citation citation, cj.sites_description judgment_sites_description, 
	    cjug.name url_group_name, 
	    cju.url, 
	    cjuf.reason, cjuf.abusetype,
	    unnest(regions) as region,
	    array_agg(distinct network_name) as networks, 
	    public.fmtime(min(first_blocked)) as first_blocked,
	    public.fmtime(max(last_blocked)) as last_blocked,
        count(distinct urls.urlid) as block_count,
        cjuf.judgment_url_id as flag_url_id
	    
	    
	from court_judgments cj 
	    left join court_judgment_urls cju on cju.judgment_id = cj.id 
	    left join court_judgment_url_groups cjug on cjug.id = cju.group_id
	    left join active_copyright_blocks urls on cju.url = urls.url 
	    left join court_judgment_url_flags cjuf on ((cju.id = cjuf.judgment_url_id and cjuf.judgment_url_id is not null) or (urls.urlid = cjuf.urlid and urls.urlid is not null))
            and cjuf.reason <> 'block_appears_correct' 

      group by cj.id, cj.date, cj.sites_description, cj.name, cj.url, cj.judgment_url, cj.case_number, cjug.id, cjug.name, cju.url,  cjuf.reason, cjuf.abusetype, region, cjuf.judgment_url_id
      order by judgment_date desc nulls last, judgment_name nulls last, url_group_name nulls last, cju.url;


create table rightsholders (
    id serial not null primary key,
    name varchar not null unique,
    address1 varchar,
    address2 varchar,
    city varchar,
    county varchar,
    postal_code varchar,
    country varchar(2) not null,
    phone varchar,
    email varchar,
    created timestamptz null,
    last_updated timestamptz
);

alter table court_judgments add foreign key (rightsholder_id) references rightsholders(id);
