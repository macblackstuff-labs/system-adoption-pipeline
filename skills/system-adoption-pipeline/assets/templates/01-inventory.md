# Pass 1 — Component inventory

Source: <the narrative you extracted from>, lines numbered with <the tool, e.g. `nl -ba`>.

Extraction lenses (Event Storming style): actors, domain events, commands, policies,
read models, external systems. A command folds into the purpose of the component that
acts on it; events, policies and read models are rows. Every uncertainty becomes a hot
spot, not a guess.

## Components

| Id | Type | Purpose | Source |
|---|---|---|---|
| C1 | agent | one line, in the source's own words | S:L42 |
| C2 | store |  | S:L51 |
| H1 | actor (external) | a human, outside the system boundary | S:L60 |

- `Id` is short and stable; every later pass refers to components by this id only.
- `Type` is free: actor, event, command, policy, read model, store, agent, external system.
  A component is outside the boundary when its `Type` begins with the word `external` or
  carries the token `(external)`, in any letter case: nobody builds it, so pass 7's checks
  1 and 2 exempt it, as a component and as an interface endpoint. `external`,
  `External system`, `actor (external)` and `EXTERNAL API` are exempt; `non-external store`,
  `internal/external bridge`, `external-facing gateway` and `externally reached` are inside
  the boundary and must be built. An id restated on several rows is one component, and it is
  outside the boundary only if every one of its rows says `external`.
- `Source` cites the line(s) the component comes from. An uncited component is a guess.

## Hot spots

| Id | What is uncertain | Source |
|---|---|---|
| HS1 |  |  |
