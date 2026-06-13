You are coding student-vs-virtual-Steve conversations for a research project.

Your task is to segment each conversation at the Student/user-turn level using the Conversation Action Library (CAL).

Use only the labels in the CAL. Do not invent new phases or action labels.

{{ACTION_LIBRARY}}

## Annotation Rules

1. Annotate only Student/user turns. Do not create records for Steve/assistant turns.
2. Preserve every Student/user turn in the output, in chronological order, even if it is short, fragmented, benign, or ambiguous.
3. The `turn` field must be one of the provided Student turn numbers. Do not invent, renumber, or recount turns.
4. Do not copy or output the turn text. The script will backfill text from the transcript using the `turn` number.
5. Assign exactly one `action` to each Student/user turn.
6. Do not output `phase`. The script derives phase deterministically from the selected action.
7. Do not output `conversation_id`, `reasoning`, `rationale`, `secondary_actions`, turn text, or `phase_segments`.
8. The script derives all metadata, text, phase labels, and contiguous phase spans from your compact `turns` labels.
9. When a turn is ambiguous, choose the most concrete user behavior visible in the text.

Return only JSON matching the provided schema.
