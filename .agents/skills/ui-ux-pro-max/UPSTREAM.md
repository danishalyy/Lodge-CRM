# Project-local Codex skill installation

Source: https://github.com/nextlevelbuilder/ui-ux-pro-max-skill
Pinned commit: 4f2dbb67e64969a9a30ab00742f2d55d66ddec2b
License: MIT (included in LICENSE).

Installed using the upstream Codex location `.agents/skills/ui-ux-pro-max`. The guidance, local CSV data, reference documents and Python search scripts are included; no application runtime dependency or remote service is added. Whitespace-only blank lines in design_system.py are normalized. Script paths in SKILL.md are adapted to this project-local Codex installation. Replace `<project-root>` with the absolute checkout path when executing commands.

Example from the repository root:

```bash
python3 .agents/skills/ui-ux-pro-max/scripts/search.py "hospitality operations dashboard minimalist" --design-system -p SafariOS
```

User choices and repository rules take precedence over generated recommendations. The accepted application specification is `docs/UI_UX_DESIGN_SYSTEM.md`, with its design master in `design-system/safarios/MASTER.md`. Do not introduce a different colour palette from a search result.
