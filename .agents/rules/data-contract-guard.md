# Data Model & Contract Guard Rule

Whenever any data model, schema, Pydantic class, TypeScript interface, or adapter mapping is created or modified:
1. You **MUST** first read and assess `docs/TEAM_DATA_CONTRACT.md` and `backend/team_contract.py` for contrast.
2. Verify that no internal component bypasses `UnifiedHotspot` / `TEAM_FIELD_MAP` or re-introduces excluded fields (such as `version`).
3. Explicitly note in your response how the proposed model change aligns with or contrasts against `docs/TEAM_DATA_CONTRACT.md`.
