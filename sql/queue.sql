CREATE ROLE queue_user;
CREATE ROLE queue_dev;

CREATE SCHEMA queue;
GRANT ALL ON SCHEMA queue TO queue_dev;
GRANT USAGE ON SCHEMA queue TO queue_user;

CREATE TYPE queue.job_status AS ENUM ('pending', 'in_progress', 'done', 'failed');
ALTER TYPE queue.job_status OWNER TO queue_dev;

CREATE TABLE queue.jobs(
	id BIGSERIAL PRIMARY KEY,
	service TEXT NOT NULL,
	payload JSONB,
	priority INT NOT NULL DEFAULT 0,
	status queue.job_status NOT NULL DEFAULT 'pending',
	created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	modified_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
	process_at TIMESTAMPTZ DEFAULT NOW(),
	reserved_at TIMESTAMPTZ,
	started_at TIMESTAMPTZ,
	finished_at TIMESTAMPTZ,
	worker_name TEXT,
	attempt_count INT NOT NULL DEFAULT 0,
	error_message TEXT
);
ALTER TABLE queue.jobs OWNER TO queue_dev;
GRANT SELECT, UPDATE, DELETE ON TABLE queue.jobs TO queue_user;

CREATE INDEX queue_jobs_service_idx
ON queue.jobs
USING btree (service);

CREATE INDEX queue_jobs_status_idx
ON queue.jobs
USING btree (status);

CREATE INDEX queue_jobs_worker_name_idx
ON queue.jobs
USING btree (worker_name);

CREATE INDEX queue_jobs_get_order_idx
ON queue.jobs
USING btree (service, priority, process_at)
WHERE attempt_count < 5 AND status = 'pending';

CREATE INDEX queue_jobs_sweep_idx
ON queue.jobs
USING btree (status, reserved_at)
WHERE status = 'in_progress';

CREATE OR REPLACE FUNCTION queue.reserve_job(
	service_arg TEXT,
	worker_name_arg TEXT,
	limit_arg INT = 1
) RETURNS TABLE(
	id BIGINT,
	service TEXT,
	payload JSONB,
	attempt_count INT,
	started_at TIMESTAMPTZ
) AS
$BODY$
BEGIN
	RETURN QUERY
	WITH reserved_jobs AS
	(
		SELECT
			jobs.id
		FROM
			queue.jobs
		WHERE
			jobs.attempt_count < 5
			AND jobs.status = 'pending'
			AND jobs.process_at <= NOW()
			AND jobs.service = service_arg
		ORDER BY
			jobs.priority DESC,
			jobs.process_at
		LIMIT
			limit_arg
		FOR UPDATE SKIP LOCKED
	)
	UPDATE
		queue.jobs
	SET
		status = 'in_progress',
		modified_at = NOW(),
		reserved_at = NOW(),
		started_at = NOW(),
		worker_name = worker_name_arg,
		attempt_count = jobs.attempt_count + 1
	FROM
		reserved_jobs
	WHERE
		jobs.id = reserved_jobs.id
	RETURNING
		jobs.id, jobs.service, jobs.payload, jobs.attempt_count, jobs.started_at;
END;
$BODY$
LANGUAGE plpgsql;
ALTER FUNCTION  queue.reserve_job(TEXT, TEXT, INT) OWNER TO queue_dev;

CREATE OR REPLACE FUNCTION queue.finish_job(
	id_arg BIGINT,
	worker_name_arg TEXT
) RETURNS INTEGER AS
$BODY$
DECLARE
	r_var INTEGER;
BEGIN
	UPDATE
		queue.jobs
	SET
		status = 'done',
		modified_at = NOW(),
		reserved_at = NULL,
		finished_at = NOW(),
		worker_name = NULL,
		error_message = NULL
	WHERE
		id = id_arg
		AND worker_name = worker_name_arg;

	GET DIAGNOSTICS r_var = ROW_COUNT;

	RETURN r_var;
END;
$BODY$
LANGUAGE plpgsql;
ALTER FUNCTION queue.finish_job(BIGINT,	TEXT) OWNER TO queue_dev;

CREATE OR REPLACE FUNCTION queue.finish_job(
	ids_arg BIGINT[],
	worker_name_arg TEXT
) RETURNS INTEGER AS
$BODY$
DECLARE
	r_var INTEGER;
BEGIN
	UPDATE
		queue.jobs
	SET
		status = 'done',
		modified_at = NOW(),
		reserved_at = NULL,
		finished_at = NOW(),
		worker_name = NULL,
		error_message = NULL
	WHERE
		id = ANY(ids_arg)
		AND worker_name = worker_name_arg;

	GET DIAGNOSTICS r_var = ROW_COUNT;

	RETURN r_var;
END;
$BODY$
LANGUAGE plpgsql;
ALTER FUNCTION queue.finish_job(BIGINT[], TEXT) OWNER TO queue_dev;

CREATE OR REPLACE FUNCTION queue.fail_job(
	ids_arg BIGINT[],
	worker_name_arg TEXT,
	error_message_arg TEXT
) RETURNS INTEGER AS
$BODY$
DECLARE
	r_var INTEGER;
BEGIN
	UPDATE
		queue.jobs
	SET
		status = CASE
			WHEN attempt_count >= 5 THEN 'failed'::queue.job_status
			ELSE 'pending'::queue.job_status
		END,
		modified_at = NOW(),
		process_at = NOW() + '1 minute'::INTERVAL * attempt_count,
		reserved_at = NULL,
		finished_at = NOW(),
		worker_name = NULL,
		error_message = error_message_arg
	WHERE
		id = ANY(ids_arg)
		AND worker_name = worker_name_arg;

	GET DIAGNOSTICS r_var = ROW_COUNT;

	RETURN r_var;
END;
$BODY$
LANGUAGE plpgsql;
ALTER FUNCTION queue.fail_job(BIGINT[], TEXT, TEXT) OWNER TO queue_dev;

CREATE OR REPLACE FUNCTION queue.sweep_stale_jobs(
	stale_after_arg INTERVAL DEFAULT '1 hour'
)
RETURNS INT AS
$BODY$
DECLARE
	r_var INTEGER;
    result_var INTEGER;
BEGIN
	UPDATE
		queue.jobs
	SET
		status = 'pending',
		modified_at = NOW(),
		reserved_at = NULL,
		worker_name = NULL,
		attempt_count = attempt_count - 1
	WHERE
		status = 'in_progress'
		AND reserved_at < NOW() - stale_after_arg
		AND attempt_count < 5;

	GET DIAGNOSTICS result_var = ROW_COUNT;

	UPDATE
		queue.jobs
	SET
		status = 'failed',
		modified_at = NOW(),
		reserved_at = NULL,
		finished_at = NOW(),
		worker_name = NULL,
		error_message = 'max retries exceeded (worker timeout)'
	WHERE
		status = 'in_progress'
		AND reserved_at < NOW() - stale_after_arg
		AND attempt_count >= 5;

	GET DIAGNOSTICS r_var = ROW_COUNT;
	result_var = result_var + r_var;

	RETURN result_var;
END;
$BODY$
LANGUAGE plpgsql;
ALTER FUNCTION queue.sweep_stale_jobs(INTERVAL) OWNER TO queue_dev;