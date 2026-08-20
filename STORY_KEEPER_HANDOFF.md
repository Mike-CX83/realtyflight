# STORY_KEEPER Handoff — adopt story custody + rescue the showcase material

You are the Claude agent in Mike's IDE. Read `CLAUDE.md` first — its Project
memory section gained two paragraphs today ("Story custody" and "Delegation
default", Mike's call, 2026-08-20). This handoff is how you take that duty up:
one standing responsibility, then a one-shot cleanup that's been waiting.

## The standing duty (permanent, not deleted with this file)

You are the custodian of RealtyFlight's story. Concretely, after every
on-machine session and push:

1. Confirm the work is recorded: the TODO item + footer reflect reality; a
   JOURNAL Part I chapter (or a dated addendum to the day's chapter) exists;
   Part II has the milestone row; Part III has an entry for anything that
   broke (symptom → root cause → fix). Backfill whatever is missing.
2. Keep presentation material safe: showcase pages, replay exports, and demo
   assets are either git-tracked or deliberately gitignored — never left
   untracked where git can't protect them.
3. You are the default executor for anything the Mac can do that the cloud
   sandbox can't: live model-API runs, pushes, SITL/live drills, venv and
   key-dependent work. Cowork builds in the cloud and hands off to you.

## One-shot — do now, in order

1. **Execute `SHOWCASE_HANDOFF.md` (repo root).** It has been waiting since
   Aug 18: verify the page renders (tiles, both replay tabs, dark mode),
   inject the real parcel boundary and refresh the abort-mission data with
   `demo/export_replay.py` per its exact commands, grep the page for secrets,
   then commit `showcase/` + `drone-mission/demo/export_replay.py`. Really
   delete `_showcase_export/` (you can `rm`; the Cowork VM cannot). Delete
   that handoff per its own instructions.
2. **Track `LAPTOP_SETUP.md`** — TODO's A-track depends on it and it is
   currently untracked. `git add LAPTOP_SETUP.md`, same commit or its own.
3. **Custody sweep #1:** `git status --porcelain` should come back EMPTY when
   you're done (nothing untracked except what Mike deliberately keeps out —
   if you find something ambiguous, list it in your report instead of
   guessing). Verify the record is current for `1c03f17` → `a0691b7` and
   today's commits — verify, don't assume.
4. **JOURNAL Part I:** append a short chapter (or extend Chapter 22 with a
   dated addendum) recording: story custody adopted, the showcase page and
   export tool rescued into git, and anything you found in the sweep. Part II
   gets a row for the showcase commit.
5. Delete THIS handoff. Surgical `git add` of exactly what you touched —
   never `-A`. House-style commit message, push, confirm CI green.

## Hard rules (mirror CLAUDE.md; binding)

- Never weaken `core/` safety code, validators, approval, or tests. The B7
  transit-altitude gap stays open until Mike decides.
- Never commit `.env`, `runs/`, `media/`, venvs, vendor/reference repos, or
  `_to_delete/`.
- Expected diff surface: `showcase/index.html`,
  `drone-mission/demo/export_replay.py`, `LAPTOP_SETUP.md`, `TODO.md`,
  `JOURNAL.md`, and the deletion of two handoffs. Explain anything beyond.
- 3-strikes rule: one error surviving 3 distinct fix attempts → stop, write
  up exactly what you tried and observed.

## Finish with a report

Showcase verdict (tiles/tabs render y/n, parcel boundary embedded y/n,
secrets grep clean), what got committed and pushed + CI status, whether
`git status` is now empty, anything ambiguous you left untracked and why,
and the one sentence Mike needs to publish the showcase page (the Netlify
drag-and-drop step from SHOWCASE_HANDOFF.md).
