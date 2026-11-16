## ADDED Requirements

### Requirement: Untrusted input boundary
The service SHALL reject explicit instruction overrides in untrusted model context and cross-origin cookie mutations without changing resources.

#### Scenario: Injected material or foreign origin
- **WHEN** untrusted text requests bypassing rules or a cookie mutation uses a foreign Origin
- **THEN** it is rejected or excluded from model context and no unauthorized resource changes occur

### Requirement: Attributable safe observations
The service SHALL record request correlation, duration and outcome without credentials; model token counts SHALL be actual provider values or unknown.

#### Scenario: Request and model execution
- **WHEN** an authenticated operation invokes a model or MCP tool
- **THEN** its safe observation carries correlation and timing while unavailable usage remains unknown

### Requirement: Reproducible delivery gates
Test and security gates SHALL run locally and in CI; images SHALL be traceable to source; benchmark and feedback evidence SHALL state actual execution scope.

#### Scenario: Gate regression
- **WHEN** an isolated known-bad regression is introduced and then repaired
- **THEN** the corresponding gate fails then passes with saved actual outputs

#### Scenario: External verification unavailable
- **WHEN** real gateway access or human feedback is unavailable
- **THEN** those items remain pending rather than reported as passed

### Requirement: Teacher grade priority
An authorized class teacher SHALL override a grade atomically, and a late model completion SHALL not overwrite it.

#### Scenario: Model finishes after teacher
- **WHEN** a teacher grades a running task before its model returns
- **THEN** the teacher score and feedback remain authoritative and the result remains unique
