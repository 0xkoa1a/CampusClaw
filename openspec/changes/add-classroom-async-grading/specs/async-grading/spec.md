## ADDED Requirements

### Requirement: Scoped assignments
Teachers SHALL manage class assignments and students SHALL submit only to their class; student responses SHALL omit teacher-only reference answers and rubrics.

#### Scenario: Classroom boundary
- **WHEN** a student creates an assignment or reads another class's assignment
- **THEN** creation returns403 and the foreign read returns404

### Requirement: Atomic idempotent acceptance
The submission endpoint SHALL atomically persist a submission, task and outbox message and return202 with task_id without calling a model.

#### Scenario: Duplicate and conflict
- **WHEN** the same user submits the same assignment and idempotency key twice
- **THEN** matching content returns the same task while changed content returns409

#### Scenario: Failure during acceptance
- **WHEN** any task or outbox insert fails
- **THEN** the transaction leaves no orphan submission or task

### Requirement: Durable bounded consumption
An independent worker SHALL publish persistent confirmed RabbitMQ messages and acknowledge successful work only after atomic result persistence; transient failures SHALL retry with bounded exponential backoff and permanent failures SHALL stop.

#### Scenario: Stopped consumer
- **WHEN** a consumer is stopped before submission and later restarted
- **THEN** acceptance still returns202, the pending task survives and eventually succeeds without resubmission

#### Scenario: Duplicate delivery and crash
- **WHEN** a message is redelivered or a running worker loses its lease
- **THEN** atomic ownership and a unique submission result prevent duplicate results and expired work is recoverable

#### Scenario: Retry exhaustion
- **WHEN** transient attempts reach the configured maximum
- **THEN** the task becomes dead, retains a safe reason and a durable dead-letter message is scheduled

### Requirement: Task visibility and grading validation
Students SHALL read only their own tasks, teachers SHALL read only their class, and the worker SHALL validate score and feedback before committing results.

#### Scenario: Invalid model output
- **WHEN** model score is boolean, non-finite or outside the assignment range
- **THEN** no result is stored and the task records permanent failure

#### Scenario: Read-only polling
- **WHEN** authorized clients poll pending or completed tasks
- **THEN** state and results are returned without invoking a model or changing the task

### Requirement: Classroom engineering and evidence
The repository SHALL retain executable engineering rules, deterministic tests, reproducible async checks and factual eighth-lesson security baseline reports, while deferring lessons9 and10.

#### Scenario: Evidence classification
- **WHEN** RabbitMQ, the real gateway or a peer is unavailable
- **THEN** reports distinguish local substitutes from real executions and preserve those checks as pending
