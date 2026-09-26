# Pass 6 — Ordering

First the walking skeleton: the thinnest end-to-end slice that exercises every layer
once. Then expand system by system in dependency order. Rolling wave — wave 1 is
decomposed to atomic steps, later waves stay at package level.

## Walking skeleton

<the slice, layer by layer, and what data contract each layer proves>

## Waves

| Wave | Packages | Detail |
|---|---|---|
| 1 | WP1, WP2 | atomic steps below |
| 2 | WP3 | package level |

## Wave 1 steps

| Step | Wave | Action | Components | Interfaces | Gaps | Blocked | Acceptance |
|---|---|---|---|---|---|---|---|
| S1 | 1 | Create the store folder and its README | C2 | IF1 |  | no | folder exists, README non-empty |
| S2 | 1 | Run the scorer once over ten real records | C1 | IF1 | G3 | no | one score file written |

- Steps are verb-led, ≤2 hours, exactly one acceptance check, no open decision embedded.
- `Gaps` lists the pass-4 gap ids the step depends on, and may also name an upstream
  wave-1 step id. If one of them is an open USER gap or a step labelled BLOCKED, `Blocked`
  must say `yes`. Pass 7 prints an advisory count of BLOCKED wave-1 steps.
- `Wave` is the wave number; only wave-1 rows are checked for acceptance checks.

## Feedback loops the order respects

<which loops exist and when each closes; a loop is not a build-order dependency>

Done-check: every wave-1 step has one acceptance check and names its components; every
package appears in exactly one wave.
