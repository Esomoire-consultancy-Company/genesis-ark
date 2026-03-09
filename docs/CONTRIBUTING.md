# Contributing to Genesis Ark

Thank you for your interest in contributing to Genesis Ark!

## Getting Started

1. Fork the repository and clone your fork.
2. Create a feature branch: `git checkout -b feat/your-feature-name`
3. Make your changes following the guidelines below.
4. Open a pull request targeting `main`.

## Branch Naming

| Type | Prefix | Example |
|---|---|---|
| Feature | `feat/` | `feat/silk-oracle-integration` |
| Bug fix | `fix/` | `fix/telemetry-pipeline-crash` |
| Documentation | `docs/` | `docs/update-architecture-diagram` |
| Chore | `chore/` | `chore/update-dependencies` |

## Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <short description>

[optional body]

[optional footer]
```

Examples:
```
feat(economics): add SILK oracle price feed
fix(telemetry): resolve Prometheus scrape timeout
docs(governance): document EmpireOS policy format
```

## Code Standards

- Validate `docker-compose.yml` changes with `make lint` before committing.
- Document all new modules with a `README.md` in their directory.
- Add new services to the platform registry (`registry/`).
- Ensure telemetry is instrumented for any new operational workflows.

## Pull Request Checklist

- [ ] Branch is up to date with `main`
- [ ] `make lint` passes
- [ ] New directories include a `README.md`
- [ ] New services are registered in `registry/`
- [ ] Telemetry events are documented in `telemetry/schemas/`
- [ ] Documentation is updated if applicable

## Code of Conduct

Be respectful, constructive, and collaborative. All contributions are welcome.
