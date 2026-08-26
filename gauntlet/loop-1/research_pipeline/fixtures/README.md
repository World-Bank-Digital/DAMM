# DAR replay fixtures

`EGY_202608260342_clean_replay_v2.json` is the frozen, reviewed response tape for the
public DAR acceptance test. Each entry is bound to the exact request and response with
precomputed SHA-256 hashes. The test reads this file as committed; it must never rewrite
the prose, reclassify figures, drop claims, or calculate replacement hashes at runtime.
The reviewed run package records this tape's whole-file SHA-256 and fixture id. Only that
exact pair may make the manifest and rendered report say `reviewed` / `Final DAR`;
alternate or live responses remain explicitly pre-review drafts.

Update the tape only when the reviewed response itself, the chapter prompt, its schema,
or the frozen Egypt run package intentionally changes. Regenerate the hashes once, review
the complete fixture diff, and then run the public CLI suite. A prompt mismatch is a test
failure, not an instruction to repair the fixture automatically.
