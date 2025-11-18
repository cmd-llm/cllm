# Explicit Command Parameter Syntax for Dynamic Commands

## Context and Problem Statement

Currently, command definitions in `available_commands` use wildcard patterns (e.g., `cat *`, `curl *`) to allow LLM-driven command execution. This approach is imprecise because:

1. **Ambiguous to LLMs**: Wildcards don't convey what arguments are expected, their types, or their semantic meaning
2. **Poor validation**: We can only check if a command starts with a pattern, not validate argument count or type
3. **Limited guidance**: The LLM gets minimal hints about what values should be provided (e.g., "is this a URL or a file path?")
4. **Inconsistent matching**: Commands like `cat <file_path>` don't match the pattern `cat *` when the LLM provides the full command

This leads to rejected commands and poor user experience when the LLM attempts to use available tools.

## Decision Drivers

- Need explicit type information for parameters (string, number, path, URL, JSON, regex)
- Want to provide semantic hints to LLMs about parameter purpose (e.g., `<string:website url>` vs. `<string:username>`)
- Must maintain backward compatibility with existing wildcard-based configurations
- Need clear validation rules for parameter matching and command execution
- LLMs should receive structured parameter hints in tool descriptions

## Considered Options

### Option 1: Wildcard-only (Current State)

Use only `*` wildcards, improve LLM context through better tool descriptions.

- Good, because no syntax changes needed
- Good, because all existing configurations remain valid
- Bad, because wildcard patterns remain ambiguous
- Bad, because we can't validate argument count or types
- Bad, because LLMs still receive minimal parameter guidance

### Option 2: Bracket Syntax Only (Breaking Change)

Replace wildcard patterns entirely with bracket syntax like `cat <path:file to read>`.

- Good, because clean, explicit syntax with clear semantics
- Good, because eliminates ambiguity entirely
- Bad, because breaks all existing configurations
- Bad, because requires migration of all current setups
- Bad, because users cannot gradually adopt the new syntax

### Option 3: Hybrid Support with Brackets (Chosen)

Support both wildcard patterns and explicit bracket syntax, with brackets providing enhanced validation and LLM guidance.

- Good, because backward compatible with existing wildcard configurations
- Good, because enables gradual migration to explicit syntax
- Good, because provides type information where needed
- Good, because LLMs get semantic hints for better argument selection
- Good, because enables richer validation without breaking changes
- Neutral, because adds complexity to command matching logic
- Neutral, because users must understand two syntaxes during transition

## Decision Outcome

**Chosen option**: "Hybrid Support with Brackets (Option 3)", because it maintains backward compatibility while enabling teams to incrementally migrate to more explicit, type-safe command definitions. This approach balances pragmatism (no breaking changes) with precision (explicit parameter types and hints).

### Consequences

- Good, because existing YAML configurations continue to work unchanged
- Good, because teams can adopt bracket syntax incrementally per command
- Good, because LLMs receive structured parameter hints (`<type:description>`)
- Good, because command validation can check parameter count and type
- Good, because syntax mirrors common documentation conventions (e.g., shell help text)
- Bad, because implementation must handle both wildcard and bracket patterns
- Bad, because documentation must cover two syntaxes during transition period
- Neutral, because migration to brackets is optional, not mandatory

### Confirmation

Success criteria for this ADR:

1. **Syntax Parsing**: Implement parser to extract parameter types and hints from bracket syntax
2. **Backward Compatibility Test**: All existing wildcard-based configurations pass validation tests
3. **Type Validation**: Commands with bracket syntax can validate argument count and basic type matching
4. **LLM Integration**: Tool descriptions include parameter hints from bracket syntax
5. **Documentation**: Updated Cllmfile.yml examples show both syntaxes and migration guidance
6. **User Feedback**: No regression in command execution success rates

## Pros and Cons of the Options

### Option 1: Wildcard-only (Current State)

Current implementation using simple glob patterns.

Example:

```yaml
available_commands:
  - command: "cat *"
    description: "Display file contents"
  - command: "curl *"
    description: "Make HTTP request"
```

- Good, because requires no implementation effort
- Good, because all existing configs are already valid
- Bad, because `cat <file_path>` doesn't match pattern `cat *`
- Bad, because LLM cannot distinguish between `cat`, `grep`, and other commands with similar signatures
- Bad, because we cannot validate that exactly 1 argument was provided
- Bad, because semantic meaning of arguments is lost (file path vs. URL vs. regex pattern)

### Option 2: Bracket Syntax Only (Breaking Change)

New explicit syntax with required parameter declarations, no wildcard support.

Example:

```yaml
available_commands:
  - command: "cat <path:file to read>"
    description: "Display file contents"
  - command: "curl -X <string:http method> <url:endpoint url>"
    description: "Make HTTP request"
```

- Good, because explicit and unambiguous
- Good, because enables strong type checking
- Good, because clear parameter hints guide LLM behavior
- Good, because eliminates confusion about what arguments are expected
- Bad, because all existing Cllmfile.yml files become invalid
- Bad, because users with dozens of command definitions must rewrite them
- Bad, because cannot be deployed without breaking existing setups
- Bad, because no graceful migration path for users

### Option 3: Hybrid Support with Brackets (Chosen)

Support both wildcard patterns and explicit bracket syntax simultaneously.

Example:

```yaml
available_commands:
  # Legacy wildcard syntax (still supported)
  - command: "git log *"
    description: "Show commit history"

  # New bracket syntax (recommended for new definitions)
  - command: "cat <path:file to read>"
    description: "Display file contents"

  # Brackets with optional hints
  - command: "curl -X POST <url:website url> --data <json:request payload>"
    description: "Submit JSON data to endpoint"
```

Parameter type system:

- `<string>` - General text argument (most flexible)
- `<string:hint>` - Text with semantic hint for LLM guidance
- `<number>` - Integer or float value
- `<path>` - File or directory path
- `<url>` - HTTP/HTTPS URL
- `<json>` - JSON data structure
- `<regex>` - Regular expression pattern

Matching rules:

1. Bracket syntax matches arguments at specific positions with type hints
2. Wildcard syntax matches using glob patterns (backward compatible)
3. Prefer bracket syntax for new commands (clear intent)
4. Deprecation warning on wildcard usage (optional, for future roadmap)

- Good, because no breaking changes required
- Good, because enables gradual migration timeline
- Good, because new configs use explicit syntax immediately
- Good, because LLMs can parse parameter types from command definitions
- Good, because teams without bandwidth for migration can continue using wildcards
- Good, because syntax is intuitive and mirrors shell help documentation
- Neutral, because command matching logic becomes more complex
- Neutral, because documentation must explain both syntaxes
- Neutral, because users may confuse which syntax applies to their situation

## More Information

### Parameter Type Reference

| Type            | Example              | LLM Guidance    | Validation                      |
| --------------- | -------------------- | --------------- | ------------------------------- |
| `<string>`      | `<string>`           | "generic text"  | None (accept any text)          |
| `<string:hint>` | `<string:api key>`   | "api key"       | None (hint only)                |
| `<number>`      | `<number>`           | "numeric value" | Must parse as int/float         |
| `<path>`        | `<path:output file>` | "output file"   | Optional: check if valid path   |
| `<url>`         | `<url:endpoint>`     | "endpoint"      | Optional: validate URL format   |
| `<json>`        | `<json:payload>`     | "JSON data"     | Optional: validate JSON syntax  |
| `<regex>`       | `<regex:pattern>`    | "regex pattern" | Optional: validate regex syntax |

### Implementation Notes

1. **Parser**: Implement regex-based parser to extract:
   - Command prefix (e.g., `cat`, `curl -X POST`)
   - Parameter positions and types
   - Optional description hints

2. **Backward Compatibility**:
   - Treat commands without brackets as wildcard patterns
   - Use existing `fnmatch` logic for backward compatibility
   - No changes to existing wildcard matching behavior

3. **Tool Description Enhancement**:
   - Extract parameter hints from bracket syntax
   - Include hints in LLM tool descriptions
   - Example: "Available parameters: file_path (path to file), recursive (boolean flag)"

4. **Validation Strategy**:
   - Count parameters in provided command
   - Match against expected parameter positions
   - Type-check parameters when type is specified
   - Provide helpful error messages when validation fails

### Example Migration Path

**Phase 1: Current (Wildcard-based)**

```yaml
available_commands:
  - command: "cat *"
  - command: "grep * *"
  - command: "curl *"
```

**Phase 2: Gradual Adoption**

```yaml
available_commands:
  - command: "cat <path:file to read>" # Migrated
  - command: "grep <regex> <path>" # Migrated
  - command: "curl *" # Still using wildcard
```

**Phase 3: Full Adoption (Future)**

```yaml
available_commands:
  - command: "cat <path:file to read>"
  - command: "grep <regex:search pattern> <path:file path>"
  - command: "curl -X <string:http method> <url:endpoint> --data <json:request>"
```

### Related ADRs

- **ADR-0013**: LLM-Driven Dynamic Command Execution (foundation for command validation)
- **ADR-0011**: Dynamic Context Injection via Command Execution (related context commands)

### Timeline

- **Week 1**: Design parameter parser and validation logic
- **Week 2**: Implement bracket syntax parsing and matching
- **Week 3**: Integrate with tool description generation
- **Week 4**: Testing, documentation, and release

### Risk Assessment

#### Technical Risks

- **Regex Complexity**: Parser complexity increases with new syntax
  - _Mitigation_: Start with simple bracket extraction, handle edge cases incrementally
- **Backward Compatibility**: Subtle regex changes could break wildcard matching
  - _Mitigation_: Comprehensive test suite for both syntaxes, regression testing
- **Performance**: More complex parsing for each command validation
  - _Mitigation_: Minimal overhead (parse once per config load, not per command execution)

#### User Adoption Risks

- **Migration Burden**: Users must learn new syntax (gradual, not required)
  - _Mitigation_: Documentation, examples, migration guide
- **Syntax Confusion**: Users may mix syntaxes incorrectly
  - _Mitigation_: Clear error messages, configuration validation

### Human Review

- **Review required**: After implementation, before release
- **Reviewers**: Core maintainers, users with complex dynamic_commands configs
- **Approval criteria**:
  1. Parser correctly handles both syntaxes
  2. All existing tests pass
  3. New syntax examples work as documented
  4. No performance regression
  5. Documentation is clear and includes migration guidance

### Feedback Log

_Completed as of November 13, 2025_

- **Implementation date**: November 13, 2025
- **Status**: Implemented and tested (Option 3 - Hybrid Support)
- **Actual outcomes**:
  - ✅ Parser extracts parameter types and hints from bracket syntax
  - ✅ Wildcard patterns continue to match as before (no regression)
  - ✅ Command validation accepts commands with correct parameter counts
  - ✅ Tool descriptions include parameter hints from bracket syntax
  - ✅ All 133 existing tests continue to pass
  - ✅ 22 new tests added for bracket syntax (total: 40 tests for tools module)
  - ✅ Backward compatibility fully maintained

- **Challenges encountered**:
  - Regex pattern needed to handle empty hints (`<type:>`) - solved by using `([^>]*)` instead of `([^>]+)`
  - Wildcard matching logic needed refinement for patterns like `ls *` - solved with explicit wildcard detection

- **Lessons learned**:
  - Hybrid approach successfully allows gradual migration without breaking changes
  - Token-based matching for bracket syntax is more precise than glob patterns
  - Parameter hints significantly improve LLM guidance quality

- **Suggested improvements**:
  - Future: Add type validation (e.g., validate that `<number>` arguments are actually numeric)
  - Future: Add optional parameter support (e.g., `<path:file>?`)
  - Future: Add deprecation warning for wildcard syntax (optional, for future roadmap)

---

## AI-Specific Extensions

### AI Guidance Level

**Strict**: Implement the decision exactly as specified in the parameter type reference and matching rules.

### AI Tool Preferences

- Preferred tools: Claude Code for implementation and testing
- Model parameters: Standard code generation settings
- Special instructions:
  1. Maintain backward compatibility with existing wildcard patterns
  2. Write comprehensive regex tests for bracket syntax parsing
  3. Test both legacy and new syntax side-by-side
  4. Include migration examples in docstrings

### Test Expectations

- Parser correctly extracts parameter types and hints from bracket syntax
- Wildcard patterns continue to match as before (no regression)
- Command validation rejects commands with wrong parameter count
- Tool descriptions include parameter hints from bracket syntax
- All 133+ existing tests continue to pass
- New test coverage for bracket syntax (at least 20 new tests)

### Dependencies

- **Related ADRs**: ADR-0013 (dynamic command execution), ADR-0011 (context injection)
- **System components**: `tools.py` (command validation), `agent.py` (command execution), `client.py` (tool description generation)
- **External dependencies**: None (uses standard Python regex)
