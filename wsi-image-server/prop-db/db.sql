CREATE TABLE data (
    id uuid PRIMARY KEY,
    path_to_file varchar(100) NOT NULL,
    converted boolean NOT NULL,
    error_msg  text NULL
);