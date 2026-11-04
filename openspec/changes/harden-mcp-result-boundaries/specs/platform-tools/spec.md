## ADDED Requirements

### Requirement: Bounded tool text
The host SHALL inspect the full tool result for known instruction patterns before truncating model-visible text at a configurable limit, and SHALL mark truncated data.

#### Scenario: Long safe result
- **WHEN** a valid tool returns text longer than the limit
- **THEN** only the bounded prefix and truncation marker are sent as tool data and generation continues

#### Scenario: Instruction after the prefix
- **WHEN** instruction patterns occur beyond the truncation boundary
- **THEN** the entire result is replaced with the fixed filtered-result notice

### Requirement: Existing-server audit attribution
The host SHALL only append standalone MCP audit records while the server reference still belongs to the authenticated class.

#### Scenario: Missing or renamed server
- **WHEN** a previously bound reference no longer resolves to its original server
- **THEN** the turn reports denial without appending an unassigned audit record

#### Scenario: Disconnected existing server
- **WHEN** the server exists but is disconnected
- **THEN** a denied outcome is recorded for that class and no remote call executes

### Requirement: Configurable bounded invocation
The host SHALL validate positive bounded round and call settings and SHALL answer using available information after reaching either budget.

#### Scenario: One-round budget
- **WHEN** the round budget is one and the model requests another tool after one round
- **THEN** only the first round executes and the final streamed answer is saved

#### Scenario: Invalid settings
- **WHEN** limits are zero, negative, boolean or exceed the documented maximum
- **THEN** application startup fails clearly
