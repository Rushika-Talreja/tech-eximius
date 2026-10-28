# DeFi Contract Auditor

Pre-deployment advisory smart contract security analysis tool.

> [!NOTE]
> This tool performs automated advisory analysis only — it does not constitute a formal audit or security certification.

## Quickstart

For architectural specifications, exit gates, and implementation decisions for Milestone M0, see **[NOTES.md](file:///Users/rushikatalreja/Documents/Hackathon/tech-eximius/NOTES.md)**.

### Local Development (Zero-Docker)
```bash
# 1. Install dependencies
make setup

# 2. Initialize local database
make migrate

# 3. Mint local test tokens (APP_ENV=local only)
make token-a
make token-b

# 4. Start API server
make api

# 5. Start Test Console
make console
```

### Running Tests
```bash
make test
```

### Pre-commit and Linting
```bash
make lint
make precommit
```

### Type Generation
```bash
# Generate OpenAPI schema and TypeScript types for web app and test console
make gen-types
make gen-console-types
```

