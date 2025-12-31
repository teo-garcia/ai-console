# Codex Skills

Add Codex skills as subdirectories with SKILL.md files:

```
skills/codex/
  my-skill/
    SKILL.md
  another-skill/
    SKILL.md
```

Each SKILL.md requires YAML frontmatter:

```yaml
---
name: my-skill
description: What this skill does
---

Skill instructions here...
```

This directory is linked to `~/.codex/skills/`.
