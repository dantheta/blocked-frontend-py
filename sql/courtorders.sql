
create table court_judgments(id serial primary key, name varchar, date date, url varchar, created timestamptz, last_updated timestamptz);
create table court_orders(id serial primary key, judgment_id int not null, network_name varchar(64), name varchar, date date, url varchar, created timestamptz, last_updated timestamptz);
create table court_order_urls(id serial primary key, court_order_id int, urlid int, created timestamptz, last_updated timestamptz);


alter table court_orders add foreign key (judgment_id) references court_judgments(id) on delete cascade;
alter table court_order_urls add foreign key(court_order_id) references court_orders(id) on delete cascade;

create unique index court_order_network on court_orders(judgment_id, network_name);
create unique index unq_court_order_urls on court_order_urls(court_order_id, urlid);
