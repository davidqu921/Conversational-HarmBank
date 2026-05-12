You are helping researchers extend a coding taxonomy for student attacks on an educational AI agent.

The deductive coding pass produced a list of `Other` notes — short descriptions of attack patterns that didn't fit any existing subtype. Your job is to:

1. **Cluster the notes** by the underlying attack pattern (not surface wording). Two notes describing the same kind of trick belong in one cluster.
2. **Propose a candidate code name** for each cluster (3–5 words, parallel in style to existing subtypes — see codebook below).
3. **Suggest the parent attack vector** for each cluster. Use existing parents when possible; only suggest a brand-new parent vector if the pattern truly doesn't fit any of the five existing ones.
4. **Write a 1-sentence definition** in the same style as existing subtype definitions.
5. **Provide 1–3 representative source notes** verbatim per cluster, with their conversation IDs, so a human can spot-check.
6. **Recommend disposition.** For each cluster, mark either:
   - `add` — clearly a recurring pattern worth a real code (typically ≥3 distinct conversations)
   - `merge` — fits an existing subtype that the deductive coder missed; name the existing subtype
   - `discard` — too rare or too vague to act on (singletons, garbled notes)

The output is a **proposal for human review**. The codebook is never modified automatically. A researcher will look at your clusters and decide.

# Existing codebook (do not propose duplicates)

{{CODEBOOK}}

# Output format

Return JSON:

```
{
  "clusters": [
    {
      "candidate_code": "string",
      "parent_vector": "Brute Force | Disguised Intent | Role Play | Structured Response | AI Attack | NEW: <name>",
      "definition": "One sentence in the codebook style.",
      "disposition": "add | merge | discard",
      "merge_into": "name of existing subtype (only if disposition=merge)",
      "n_conversations": <int>,
      "examples": [
        {"conversation_id": "...", "note": "..."},
        ...
      ]
    },
    ...
  ],
  "summary": "2-3 sentence overview of what the discovery pass found."
}
```
