# Contributing

Thanks for wanting to help! sillon is a monorepo hosted at
[github.com/balerat/sillon](https://github.com/balerat/sillon). First get a working dev
environment by following the [Development setup](development.md).

## Workflow

1. **Claim an issue** on GitHub and move it to *In Progress*.
2. **Branch** off `develop` with a descriptive name:
   ```bash
   git checkout -b feature/name_of_the_feature
   ```
3. **Write code** — see the [Architecture](architecture.md) for how the pieces fit together.
4. **Test** from the repo root:
   ```bash
   make test          # or: pytest packages/*/tests packages/interface/*/tests
   ```
5. **Open a Pull Request** into `develop` once tests pass.

> **⚠️ Never push directly to `main`.** All changes go through a PR into `develop` first.

## Conventions

- Public APIs are documented with Google-style docstrings — the
  [API reference](../reference/sillonpy.md) and the internal reference are generated from them, so
  keep docstrings accurate when you change behavior.
- Add or update tests for any behavior change; the synthetic-project fixtures in
  `packages/interface/sillonlab/tests` and `packages/interface/cli/tests` are the easiest way to
  test engine/CLI behavior without a running server.
