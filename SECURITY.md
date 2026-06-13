# Security Policy

## Reporting a vulnerability

Please **do not open a public issue** for security problems. Use GitHub's
private vulnerability reporting on this repository ("Security" tab →
"Report a vulnerability"), or email **admin@trugs.ai** if private reporting
is unavailable.

You can expect an acknowledgement within a few business days. Please include
a reproduction (the TRUG input and the operations run) where possible.

## Supported versions

Only the **latest released version** of `trugs-store` receives security
fixes.

## Scope notes

trugs-store is a storage library operating on graphs your application
supplies. Reports about malicious graph payloads causing unexpected code
execution, SQL injection through the PostgreSQL backend, path traversal in
the JSON file persistence, or resource exhaustion are explicitly in scope.
