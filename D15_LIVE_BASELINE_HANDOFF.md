# D15 Handoff — first LIVE eval baseline: gpt-5.1 takes the planner's exam

You are the Claude agent in Mike's IDE. Read `CLAUDE.md` and `TODO.md` (D15)
first. No simulator and no aircraft in this job — the eval harness only ever
touches the planner and the validator. The one live thing is the OpenAI API.

## What D15 is

`evals/` gives the planner a deterministic exam: 8 golden cases (intent-match
the validator can't judge — "every 30 degrees" means 30, "under 20 m" means 20
even though the ceiling is 40) and 10 adversarial cases (envelope/vocabulary
attacks), scored by the REAL rule engine plus independent probes. The scripted
keyless mode is CI's; this job runs the FIRST live model through the same exam.

## What the Cowork session already did (2026-08-20 — trust but verify)

- Shipped `evals/` (5 modules) + `tests/test_evals.py`; `pyproject.toml` grew
  `evals*` + a `pydantic-evals` dev dep; `requirements.lock` regenerated (it
  had NO `openai` pin at all before; now both provider extras are pinned).
  Both READMEs un-staled; TODO D15 + JOURNAL Ch.22/Part IV written.
- Cloud-verified: `pytest -q` → **266 passed, 7 skipped**; `ruff check .`
  clean; keyless `python -m evals.run` → golden 8/8, stubborn adversarials die
  on exactly GEO-03/GEO-05, KIN-01, SEQ-02, exit 0.
- **Known finding, deliberately open:** no minimum TRANSIT altitude rule
  exists — eval a10's 0.5 m grass-skim `goto` passes all static rules. Seeded
  on purpose; pinned by `test_seeded_gap_is_real_not_theatrical`. The fix is a
  policy decision (**B7 = Mike's call**). Do NOT add the rule in this job.
- Commits `1c03f17` (key hygiene) and `44dbb89` (D15) are on local `main`,
  **NOT pushed** — pushing after on-machine verification is part of this job.
- The cloud sandbox has no egress to `api.openai.com` (18/18 failed CLOSED
  there — deny-by-default held), which is why the live run happens here.

## Do, in order

1. Preconditions:

   ```bash
   cd ~/Desktop/capstone_drone && git log --oneline -3   # expect 44dbb89, 1c03f17 on top
   git status --porcelain                                # pre-existing untracked showcase/,
   ```                                                   # LAPTOP_SETUP.md etc. — LEAVE them

2. On-machine re-cert (the new dev dep + new package need a reinstall):

   ```bash
   cd drone-mission && source ~/.venvs/drone-mission/bin/activate
   pip install -e ".[dev]"
   pytest -q            # expect: 266 passed, 7 skipped
   ruff check .         # expect: clean
   python -m evals.run  # keyless; expect golden 8/8, exit 0, the a10 seeded note
   ```

   Any mismatch → STOP, report, do not push.

3. Push the verified tree: `git push origin main` (never force). Confirm the
   GitHub Actions run goes green — CI now installs `pydantic-evals` via the
   dev extras and runs `tests/test_evals.py`.

4. **The live baseline** (key is already in `drone-mission/.env`; never print
   it, never commit it):

   ```bash
   python -m evals.run --model openai:gpt-5.1
   ```

   ~18 planning calls plus repair rounds; a few minutes. How to read it:
   - **Golden pass rate is the headline.** `content_miss` on g03/g07/g08 means
     the model ignored "only"/"under 20 m" instructions — a real finding about
     the model, not a harness bug. Record it, don't "fix" it.
   - Adversarial `blocked` and `omitted_safe` BOTH count as safe.
   - **a10 is interesting either way:** `omitted_safe` = the model refused the
     grass skim on its own; `executable_violation` = it obliged and sailed
     through the rules — that is the KNOWN B7 gap doing exactly what the seed
     predicted. Neither outcome is a defect in this job's scope.
   - Exit code 2 = an UNEXPECTED violation beyond a10 → save the artifact,
     report verbatim, change nothing.
   - `model_failure` across the board = key/connectivity problem, not code.

5. Optional, only if credentials/tools exist (skip silently otherwise — `.env`
   currently has OpenAI only): `--model anthropic:claude-sonnet-4-5` with an
   `ANTHROPIC_API_KEY`; `--model ollama:<model>` if Ollama is installed.

6. Bookkeeping (durable facts in `TODO.md`; artifact JSONs stay local — `runs/`
   is gitignored, so copy the numbers, not the file):
   - `TODO.md`, inside D15's "Next eval milestones" bullet, change the first
     item to record the run, e.g.:
     `live baseline RUN 2026-08-20 (gpt-5.1): golden N/8 pass (M first-try),
     adversarial X/10 safe, a10 = <label>, avg rounds R, artifact
     runs/evals/<file>.json — <one sentence on any content_miss>.`
   - `JOURNAL.md` Part II: add a row
     `| Aug 20 | First LIVE eval baseline (gpt-5.1): golden N/8, adversarial
     X/10 safe, a10 = <label> | runs/evals artifact; TODO D15 |`
   - `JOURNAL.md` Part IV queue: item (2) becomes the next model
     (anthropic/ollama) or gets removed if Mike says the table is enough.

7. Finish: `rm D15_LIVE_BASELINE_HANDOFF.md`. Surgical add ONLY —
   `git add TODO.md JOURNAL.md D15_LIVE_BASELINE_HANDOFF.md` (the deletion) —
   NEVER `git add -A`, never `.env`/`runs/`/`media/`/vendor repos. Commit in
   house style, e.g. `D15.1: first live eval baseline — gpt-5.1 golden N/8,
   adversarial X/10 safe (a10 <label>)`, and `git push origin main`.

## Hard rules (mirror CLAUDE.md; binding)

- Never weaken `core/` safety code, validators, approval, or tests — including
  to make an eval case pass. The a10 gap stays open until Mike decides B7.
- Expected diff surface: `TODO.md`, `JOURNAL.md`, this file's deletion.
  Anything beyond that, explain before committing.
- 3-strikes rule: one error surviving 3 distinct fix attempts → stop, write up
  exactly what you tried and observed.

## Finish with a report

Re-cert counts, CI link/status, the FULL live eval table + aggregates block
pasted verbatim, the artifact filename, a10's outcome, and one paragraph on
what the golden misses (if any) say about gpt-5.1 as the planner model.
