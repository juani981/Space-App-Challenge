# Data Model & Contract Guard Rule

Whenever any data model, schema, Pydantic class, TypeScript interface, side panel, or adapter mapping is created or modified:
1. You **MUST** first read and assess `docs/TEAM_DATA_CONTRACT.md` and `backend/team_contract.py` for contrast.
2. Verify that no internal component bypasses `UnifiedHotspot` / `TEAM_FIELD_MAP` or re-introduces excluded fields (such as `version`).
3. **GOLDEN RULE — Extensible Side Panel Contract (Open/Closed Principle):**
   - The contract consumed by the right-hand side panel (`HotspotSidePanel`) **MUST always be extensible (ampliable)**.
   - Neither `UnifiedHotspot` nor `HotspotSidePanel` may lock the system into a rigid, closed set of fields. New primary attributes or processed analysis metrics delivered by Teammates 1 & 2 must be able to plug in dynamically (via declarative field descriptors and/or an extensible `analysis_data` key-value map) without rewriting the panel's layout logic.
4. Explicitly note in your response how the proposed model or UI change aligns with `docs/TEAM_DATA_CONTRACT.md` and this Golden Rule.
