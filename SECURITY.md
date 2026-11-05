# Security policy

* This repository contains **no credentials** and must never receive any. It needs no secrets:
  CI runs offline unit tests with a read-only token.
* Do not add code that talks to a marketplace, shop, cloud storage or AI service, and do not add
  workflow secrets. This repository is a library of offline tools, not an automation runner.
* Workflows use `permissions: contents: read`, pinned action SHAs, `persist-credentials: false`,
  and never `pull_request_target`.
* Report a vulnerability privately through GitHub's *Report a vulnerability* (Security tab).
