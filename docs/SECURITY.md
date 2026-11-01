# Security and privacy

## Data collection

LinuxOps uses psutil to read overall CPU load, logical core count, RAM and swap utilization, filesystem usage for one configured directory, total bytes/packets received and sent, and boot age. It does not read files or inventory users, processes, local IPs, open connections, environment secrets or SSH credentials.

Network metrics are **aggregate counters**. There is no packet capture, external request, automated host discovery or port scanning. A user's own browser fetches API data from the same loopback host.

## Network boundary

The native web server binds to `127.0.0.1` by default, and the CLI deliberately rejects public listening addresses. There is no authentication. Never publish this server to the internet or another person's network.

The Docker demonstration maps host loopback port 8765 to a container-bound API. Its data can reflect container limits and must be labeled accordingly.

## Files and retention

SQLite stores the bounded numeric samples under the current user's local data directory by default. The model automatically prunes samples older than seven days on further writes. No cleanup occurs while the program is stopped. The database directory permissions depend on the operating system and umask, so users should keep the directory private when working on multiuser systems.

CSV export may contain information about system usage. Store it as local operational data, not public GitHub content. Database file patterns are excluded from Git by `.gitignore`.

## Ansible

The sample inventory includes only localhost. Using the sample playbook against real network machines requires explicit owner authorization, approved SSH access and information handling. The playbook collects standard Ansible system facts; unlike the primary collector, that may disclose additional machine identifiers. Never run remote playbooks casually against customer environments.

## Production blockers

This is a learning project and not hardened production monitoring. Before a multi-host service, add user authentication, TLS, per-tenant authorizations, data encryption and backups, access logs, rate limiting, secret rotation, and explicit customer approval.

No configuration changes, privilege escalation, remote shells or remediation workflows are included in the local collector.
