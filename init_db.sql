CREATE SCHEMA IF NOT EXISTS test_project;

CREATE TABLE IF NOT EXISTS test_project.number_tb (
    person_id varchar(20) not null,
    good_number int8 not null,
    UNIQUE(person_id, good_number)
);
