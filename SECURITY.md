# Security

TraceLens is designed for local and controlled demonstration use. The application handles untrusted log files and can contain sensitive operational data. The Compose example binds the frontend to loopback and leaves the backend on the internal container network.

Report suspected vulnerabilities privately to the maintainer using the repository's private vulnerability reporting feature, if enabled, or a private contact channel provided by the maintainer. Include the affected version, reproduction steps, impact and a synthetic sample. Keep credentials, personal information, and private log records out of public issues.

The application uses input validation, upload handling and size limits, configured CORS origins, and parameterized ORM queries. It performs best-effort matching for common secret patterns. Review logs before ingestion and reports before sharing. Broader deployment needs authentication, authorization, TLS, storage protections, abuse controls and an operational data-retention policy.
