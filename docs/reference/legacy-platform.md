# Legacy Platform Vision — Deferred

This repo previously described a broader Contralatam Agent platform:

- OCDS + SUNAT + CGR + ONPE + JNE collectors.
- FUNES 23 indicators.
- Entity graph and ConflictMap.
- Civic Amplifier Engine.
- SMS distribution and national map.

That direction is not deleted from product memory, but it is deferred until the hackathon MVP proves the TDR Scanner core.

Current MVP truth:

```text
AgentePerry TDR Scanner = TDR ingestion -> PDF parsing -> chunks -> embeddings -> rule-based flags -> dossier API
```

Do not reactivate legacy platform work without a new spec moved from `specs/deferred/` to `specs/active/`.
