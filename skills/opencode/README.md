# OpenCode Skills

Add OpenCode skills as subdirectories with SKILL.md files:

```
skills/opencode/
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

This directory is linked to `~/.config/opencode/skills/`.
