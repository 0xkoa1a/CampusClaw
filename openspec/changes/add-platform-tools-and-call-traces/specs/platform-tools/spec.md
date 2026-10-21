## ADDED Requirements

### Requirement: Application configuration
The platform SHALL offer multiple applications, reusable prompt templates, built-in skills and uploaded skills, with class-scoped teacher configuration.

#### Scenario: Teacher selects a template
- **WHEN** a teacher selects a built-in template and saves an application
- **THEN** its role prompt is persisted and included in subsequent model messages

#### Scenario: Student cannot alter configuration
- **WHEN** a student writes an application or skill configuration
- **THEN** the server returns 403

### Requirement: Bounded external tools and MCP
The server SHALL expose only tools bound to the current application, execute validated tool requests, and return results to the model.

#### Scenario: MCP tool execution
- **WHEN** the model requests an allowed MCP calculation
- **THEN** the host calls its class-scoped connected HTTP MCP service with server-side Bearer authentication, validates arguments against the discovered schema, and returns results as untrusted data to the model

#### Scenario: Invalid or unbound calls
- **WHEN** the model requests an unbound tool, malformed arguments or exceeds the call budget
- **THEN** no unauthorized operation executes, a denied or error record is emitted before answer text, and the model answers with available information

### Requirement: HTTP service and managed discovery
The repository SHALL include an HTTP MCP service with health, initialize, tools/list and tools/call, at least two tools and server-side Bearer authentication, started with the host by Compose.

#### Scenario: Discovery and disconnect
- **WHEN** a teacher registers an allowed Base URL and connects using an environment token
- **THEN** the current discovered tools replace the cached list and only token configuration status is returned
- **WHEN** the teacher disconnects
- **THEN** the cache is cleared and its tool references cannot execute

#### Scenario: Skill reference validation and audit
- **WHEN** a teacher saves a tool@server skill reference
- **THEN** the server validates class ownership, connected state and discovered tool existence, and subsequent invocations appear in class-scoped teacher audit

#### Scenario: Bounded execution
- **WHEN** model tool calls reach the round, count or time budget
- **THEN** the host stops executing tools and streams a final answer from existing context

### Requirement: Owned call evidence
The server SHALL record actual model request bodies, upstream responses and tool results without transport credentials, and SHALL enforce conversation ownership when reading them.

#### Scenario: Request and response inspection
- **WHEN** the owner reads a completed turn's trace
- **THEN** the trace includes model, messages, generation parameters, tool schemas when enabled, upstream data and final stored output

#### Scenario: Isolation and deletion
- **WHEN** another user reads a trace or the owner deletes its conversation
- **THEN** unauthorized reads return 404 and conversation deletion removes its traces

### Requirement: Context inclusion verification
The deliverable SHALL verify prompt, knowledge, skill and MCP inclusion using synthetic input and actual recorded calls, and provide the Git repository URL and project introduction in a PDF report.

#### Scenario: Knowledge and skill comparison
- **WHEN** a synthetic corpus contains relevant and irrelevant passages and two skills are bound
- **THEN** recorded messages show retrieved passages and the selected skill body, while excluded passages and unselected skill bodies are absent

#### Scenario: Evidence accuracy
- **WHEN** a real gateway is unavailable
- **THEN** deterministic test results remain explicitly labeled as tests and are not reported as real model evidence
