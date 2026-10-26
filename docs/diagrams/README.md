# PlantUML diagrams

These describe the current implementation, rather than a proposed future design.
Editable `.puml` sources and rendered SVGs are kept together so the documentation
works without a PlantUML browser plugin or external rendering service.

- [Architecture](architecture.svg) · [source](architecture.puml): agent interface, storage, retrieval and decision-provider boundaries.
- [Project initialization](project-init.svg) · [source](project-init.puml): interactive and unattended setup, preservation and client registration.
- [Recall](recall.svg) · [source](recall.puml): bank, durable notes and original evidence combined for the coding agent.

Regenerate from the repository root with PlantUML, Java and Graphviz installed:

```bash
JAVA_TOOL_OPTIONS=-Djava.awt.headless=true plantuml -tsvg docs/diagrams/*.puml
```

Rendering is local. Review the generated SVGs whenever the source changes.
