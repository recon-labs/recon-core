# Compatibility Change Checklist

## Purpose

Use this checklist whenever a change touches a public contract surface from
`docs/compatibility/public-contract-inventory.md`.

The goal is to make compatibility impact explicit before implementation and
review. This checklist is a process guide; it is not a CI gate.

## Checklist

### Milestone and planning impact

- [ ] Confirmed any milestone implementation has current lightweight prework
      matching `docs/planning/milestone-process.md`.
- [ ] For high-risk milestones or public-surface changes, added or updated a
      dimension-expanded acceptance/conformance matrix before implementation.
- [ ] Mapped every required conformance matrix row to a new test, existing test,
      or explicit out-of-scope rationale.
- [ ] Checked whether the requested milestone is too broad, spans multiple
      high-risk surfaces, or should be dissolved into decimal sub-milestones such
      as `Milestone N.1`, `Milestone N.2`, and `Milestone N.3`.
- [ ] Confirmed every proposed decimal sub-milestone is implementation-bearing
      and no sub-milestone has a build scope that is only design, research, ADRs,
      matrices, documentation, gates, or alignment work.
- [ ] For required high-risk splits, produced a Split Assignment Matrix with one
      row per implementation sub-milestone and assigned gates, ADRs/decisions,
      docs updates, acceptance/conformance matrix rows, BDD/workflow scenarios,
      tests, public contract surfaces, phase-exit requirements, and blockers to
      the exact sub-milestone they govern.
- [ ] Ran an orphan check proving no gate, ADR, docs update, matrix row, BDD
      scenario, public contract concern, test requirement, or phase-exit
      requirement remains assigned only to the umbrella milestone.
- [ ] Updated roadmap, build-order, gate, ADR, and compatibility references when
      a milestone was split so no orphan implementation plan remains.

### ADR impact

- [ ] Checked whether the change affects a durable decision.
- [ ] Added or updated an ADR when the change affects public syntax, artifact
      formats, adapter interfaces, validation defaults, package semantics,
      evidence behavior, major architecture, or product scope.
- [ ] Linked the ADR from the relevant docs when useful.

### Documentation impact

- [ ] Updated framework docs for public behavior changes.
- [ ] Updated architecture docs for boundary or interface changes.
- [ ] Updated implementation docs for build guidance changes.
- [ ] Updated user-facing docs when CLI, YAML, evidence, or workflow behavior
      changed.
- [ ] Updated `docs/compatibility/public-contract-inventory.md` when a public
      surface was added, removed, renamed, stabilized, or changed.
- [ ] Checked whether diagnostic code, message, redaction, path,
      `resource_type`, `resource_name`, `line`, `column`, hint rendering, or
      future structured diagnostic fields changed for any public output surface.
- [ ] Checked whether raw parser, adapter, database, runtime, or evidence
      writer exception text can quote authored YAML snippets, source/target
      query text, relation names, row values, rendered profile values,
      credentials, or other private literals in CLI output, logs, artifacts,
      reports, or test snapshots.
- [ ] Checked whether generated artifact cleanup, publish ordering, stale
      output removal, or partial-write behavior changed for any generated
      artifact surface.
- [ ] Checked whether execution placement changed across operation execution
      location, comparison location, materialization/staging policy, Python
      fallback behavior, or unsupported-placement diagnostics.
- [ ] Checked whether result/evidence sink placement changed across sink mode,
      source/target/third destination ownership, sink requiredness,
      sink-write status, table schema/versioning, migration, idempotency,
      retry, retention, partial-write behavior, or local-output optionality.
- [ ] Checked whether privacy/redaction rules changed for terminal output,
      logs, diagnostics, run results, evidence, reports, failure details,
      result tables, state references, or adapter test-kit snapshots.
- [ ] Checked whether render-sql requests that fail before adapter rendering
      still write accurate `rendering.status` metadata instead of implying
      rendering was not requested.

### Changelog impact

- [ ] Updated `CHANGELOG.md` under `Unreleased` for user-visible behavior or
      public contract changes.
- [ ] Put bug fixes under `Fixed`, new capabilities under `Added`, and changed
      semantics or defaults under `Changed`.
- [ ] Explicitly explained why no changelog entry is needed when the touched
      area is public-risk but the change is internal only.

### Migration impact

- [ ] Checked whether users, adapter authors, package authors, CI workflows, or
      artifact readers must change anything.
- [ ] Added migration or deprecation guidance when behavior is breaking or
      requires project changes.
- [ ] Updated compatibility docs and release notes when support ranges changed.

### Test-kit impact

- [ ] Checked whether future or existing adapter test-kit expectations are
      affected.
- [ ] Updated adapter test-kit docs or expectations when adapter API,
      capability, typed operation, SQL rendering, metadata, or execution
      behavior changed.
- [ ] Checked profile-backed adapter routing behavior: connection `type` must
      stay a literal non-empty adapter type, templated `{{ ... }}`,
      `{% ... %}`, `{# ... #}`, or `env_var(...)` `type` values must fail
      before adapter resolution, adapter factories/renderers must not be
      invoked, resolved adapter `adapter_type` metadata must match the literal
      profile `type` before renderer selection or execution, and no rendered
      environment value may appear in diagnostics or artifacts.
- [ ] Checked profile env-var rendering conformance for non-routing connection
      fields: `{{ env_var(...) }}` and bare `env_var(...)` forms, defaults,
      missing variables, unsupported bare expressions, embedded env-var calls,
      filters, and unsupported template fragments such as `{% ... %}` and
      `{# ... #}` must either render safely or fail before adapter resolution
      instead of surviving as literal config.
- [ ] Updated adapter diagnostic expectations when diagnostic messages,
      redaction behavior, or adapter-provided diagnostic fields changed.
- [ ] Checked diagnostic-code redaction for unsafe config keys and rendered
      profile values in delimiter-separated and separatorless forms, including
      key-shaped and value-shaped cases such as `RC_PASSWORD_LEAK`,
      `RCPASSWORDLEAK`, `RCsuper-secretLEAK`, and `RC12LEAK`.
- [ ] Checked safe diagnostic-code preservation: adapter codes with incidental
      non-secret config-key substrings, such as
      `RC_ADAPTER_CAPABILITY_UNSUPPORTED`, must not be suppressed.
- [ ] Checked adapter factory diagnostic field-shape conformance when adapter
      resolution is involved: invalid `Diagnostic` field values, including
      string severities, empty or non-string `code` or `message`, non-string
      optional context fields, and non-integer `line` or `column`, must become
      `RC_ADAPTER_RESOLUTION_FAILED` before redaction, rendering, artifact
      writing, or execution consumes them.
- [ ] Checked case-variant and simple-transformation redaction cases when
      adapter diagnostics can reference rendered profile config in diagnostic
      code, message, hint, path, `resource_type`, `resource_name`, `line`,
      `column`, or future structured diagnostic fields.
- [ ] Checked numeric diagnostic-field redaction for short rendered scalar
      profile values and equivalent formatted variants, such as `port: 12`,
      `12.0`, `+12`, and `1.2e1`, not only long secret-like tokens.
- [ ] Checked parsed DSN component and derived-fragment redaction when
      rendered connection strings are in scope: username, password, host, path,
      query values, percent-decoded values, and substrings must not leak through
      diagnostics, generated artifacts, logs, run results, evidence, or adapter
      test snapshots.
- [ ] Checked whether any shared adapter test-kit compile-flow harness must
      assert `RC_ADAPTER_RENDERING_BLOCKED_BY_COMPILE_DIAGNOSTICS` and no
      adapter invocation when compile validation already failed.
- [ ] Checked whether any public/shared helper or test-kit harness accepts both
      a resolved adapter and explicit renderer, and if so whether adapter API
      compatibility and renderer `adapter_type` binding are validated before
      `render_plan()` is invoked.
- [ ] Checked whether rendered SQL step `required_capabilities` are enforced
      before SQL artifacts, run results, evidence, or adapter test snapshots are
      published when shared renderer/test-kit or adapter compatibility is
      claimed.
- [ ] Checked whether adapter setup diagnostics can coexist with independent
      render diagnostics in the same compile invocation, and whether service or
      CLI diagnostics preserve both instead of reporting only setup failures.
- [ ] Checked source/target privacy cases for raw adapter, database, and
      runtime exception text before any adapter test-kit or external adapter
      repository claims execution, diagnostics, run-result, evidence, report,
      log, or snapshot compatibility.
- [ ] Checked execution-placement conformance before any adapter, shared test
      kit, or external repository claims source-side, target-side,
      same-context, adapter-managed intermediate, external comparison-engine,
      or Recon-local fallback compatibility.
- [ ] Checked materialization/staging conformance before any adapter claims
      temporary staging, extracts, loads, table-to-table copy, cleanup,
      row/memory limits, or large-result movement compatibility.
- [ ] Checked result/evidence sink-write conformance before any adapter claims
      table-create, migration, append, upsert, merge, transactional batch
      write, metadata, or staging-for-sink compatibility.
- [ ] Documented unsupported capability behavior when adapters are not required
      to implement a new operation.

### Compatibility matrix impact

- [ ] Updated `docs/compatibility/compatibility-matrix.md` when version support,
      artifact versions, typed plan support, adapter API support, capability
      support, package support, or integration status changed.
- [ ] Updated `docs/compatibility/compatibility-matrix.md` when execution
      placement, comparison placement, materialization/staging, result/evidence
      sink mode, result table schema, or adapter write/sink compatibility
      changed.
- [ ] Added a new compatibility dimension when the change introduced one.

### Version constant impact

- [ ] Added or updated a code version constant only when code can produce,
      consume, validate, or reject that versioned surface.
- [ ] Avoided placeholder constants for surfaces that are only planned.
- [ ] Updated `docs/compatibility/artifact-versions.md` when artifact version
      constants changed.

## Review note

If a checklist item is not applicable, say why in the pull request notes. The
expected outcome is explicit reasoning, not unnecessary documentation churn.
Reviewers should treat missing milestone prework, example-only high-risk matrix
coverage, uncovered required matrix rows, or missing split justification as
material process risks for public-surface changes.
