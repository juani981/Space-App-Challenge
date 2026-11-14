---
name: baby-steps-guide
description: >-
  Guides the user through building the web application in small, incremental
  baby steps. Use this skill whenever proposing, explaining, or implementing
  any code or architectural change, ensuring every step explicitly justifies
  how it brings the project closer to the goal in AGENTS.MD while keeping the
  user in full control.
---

# Baby Steps Development & Goal Justification Skill

Follow this workflow whenever guiding or implementing changes in this project:

## Core Protocol
1. **One Baby Step at a Time:** Never scaffold multiple layers or files at once without explicit approval. Propose or execute only one small, self-contained increment per turn.
2. **Mandatory Goal Justification:** Every single proposal or step MUST include a clear **Goal Justification** block explaining:
   - **What this baby step does** (in 1–2 sentences).
   - **How it approaches the final goal** (connecting the interactive map AOI, the backend API, and the future Burning Activity Calendar / CSV export).
   - **How to verify it immediately** before moving to the next baby step.
3. **Wait for User Control:** After presenting or completing a single baby step, stop and let the user verify or approve before advancing to the next step.
