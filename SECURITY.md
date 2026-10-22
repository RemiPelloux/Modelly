# Security policy

## Supported versions

Only the latest minor release on PyPI (`modelly-abm`) receives security fixes. Upgrade before
reporting: `pip install -U modelly-abm`.

## Reporting a vulnerability

Please do not open a public issue for a security problem.

Use GitHub's private vulnerability reporting instead:
<https://github.com/RemiPelloux/Modelly/security/advisories/new>. It reaches the maintainer only,
and the report becomes a draft advisory where the fix and the credit are coordinated with you.

Include what you can: the affected version, a minimal reproduction, and the impact as you
understand it. You will get an acknowledgement within a week, and a fix or a decision within
30 days for anything confirmed.

## Scope

Modelly executes the model code you write and loads data you provide. Bugs in your own model, or
in notebooks you run, are not vulnerabilities in Modelly. Problems in the framework itself, in its
visualization server, in the `python -m modelly.migrate` codemod, or in the release pipeline are.
