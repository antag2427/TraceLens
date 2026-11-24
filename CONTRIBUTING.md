# Contributing

Use a local clone and create a branch for each change. Install the backend and frontend dependencies using the [README](README.md). Run Pytest, TypeScript checking, ESLint and the Vite production build before submitting a pull request.

Describe the user-facing behavior, the evidence behind any analysis change, and exactly which checks you ran. Update the API or methodology documentation when a contract or scoring decision changes. Changes to ingestion, ML or incident correlation should include a regression test for any behavior that the existing suite does not cover. Use synthetic fixtures and temporary SQLite databases for test cases.

Keep local databases, environment files, private logs and generated build artifacts out of commits. If a change affects the demo fixture, regenerate it with the repository generator and explain the intended scenario change.
