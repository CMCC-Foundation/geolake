-- CREATE USER dds WITH PASSWORD 'dds';
-- CREATE DATABASE dds;
-- GRANT ALL PRIVILEGES ON DATABASE dds TO dds;

-- extension for using UUID column type
CREATE EXTENSION "uuid-ossp";

CREATE TABLE IF NOT EXISTS users (
    user_id uuid DEFAULT uuid_generate_v4() PRIMARY KEY,
    api_key VARCHAR(255) UNIQUE NOT NULL,
    contact_name VARCHAR(255)
);

CREATE TABLE IF NOT EXISTS roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR (255) UNIQUE NOT NULL
);

CREATE TABLE IF NOT EXISTS users_roles (
    ur_id SERIAL PRIMARY KEY,
    user_id uuid NOT NULL,
    role_id SERIAL NOT NULL,
    CONSTRAINT fk_user
        FOREIGN KEY(user_id) 
            REFERENCES users(user_id),
    CONSTRAINT fk_role
        FOREIGN KEY(role_id) 
            REFERENCES roles(role_id)              
);

CREATE TABLE IF NOT EXISTS workers (
    worker_id SERIAL PRIMARY KEY, 
    status VARCHAR(255) NOT NULL, 
    host VARCHAR(255),
    dask_scheduler_port INT,
    dask_dashboard_address CHAR(10),
    created_on TIMESTAMP NOT NULL
);

CREATE TABLE IF NOT EXISTS requests (
    request_id SERIAL PRIMARY KEY, 
    status VARCHAR(255) NOT NULL, 
    priority INT,
    user_id uuid NOT NULL,
    worker_id INT,
    dataset VARCHAR(255),
    product VARCHAR(255), 
    query json,
    estimate_size_bytes BIGINT,
    created_on TIMESTAMP NOT NULL,
    last_update TIMESTAMP,
    fail_reason VARCHAR(1000),
    CONSTRAINT fk_user
        FOREIGN KEY(user_id) 
	        REFERENCES users(user_id),
    CONSTRAINT fk_worker
        FOREIGN KEY(worker_id) 
	        REFERENCES workers(worker_id)
); 

CREATE TABLE IF NOT EXISTS downloads (
    download_id SERIAL PRIMARY KEY,
    download_uri VARCHAR(255),
    request_id INT UNIQUE,
    storage_id INT,
    location_path VARCHAR(255),
    size_bytes BIGINT,
    created_on TIMESTAMP NOT NULL,
    CONSTRAINT fk_req
        FOREIGN KEY(request_id) 
	        REFERENCES requests(request_id) 
);

CREATE TABLE IF NOT EXISTS storages (
    storage_id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    host VARCHAR(20),
    protocol VARCHAR(10),
    port INT
);