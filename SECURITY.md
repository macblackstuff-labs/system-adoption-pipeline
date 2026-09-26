# Security policy

## Supported version

Only the latest release is supported. The first release is v0.1.0. Fixes land on `main` and ship
in the next release; there are no patches for earlier tags.

## Reporting a vulnerability

Report privately through GitHub's private vulnerability reporting for this repository:
open [**Security → Report a vulnerability**](https://github.com/macblackstuff-labs/system-adoption-pipeline/security/advisories/new).
That opens a draft advisory visible only to you and the maintainers. Private vulnerability
reporting is enabled on this repository as of the moment it becomes public, so this link works
for anyone. Please do not open a public issue or pull request for a vulnerability.

Include what you have: the affected file or command, what an attacker gains, and the smallest
reproduction you can manage. Expect a first response within 14 days. If the report is confirmed,
the fix and an advisory are published together, crediting you unless you ask otherwise.

## Scope

This repository ships an Agent Skill: Markdown instructions an agent reads, and Python scripts a
user runs on their own machine over their own files. In scope: anything in this repository that
can read, write or execute outside the files the operator pointed it at, or that makes an agent
take an action the instructions do not describe. Out of scope: the agent harnesses that load the
skill, the `skills` CLI used to install it, and GitHub itself — report those to their own projects.
