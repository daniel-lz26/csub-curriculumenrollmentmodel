# Project Map — a plain-English guide to this repo

This page is for anyone who landed in this GitHub repository and isn't a
software developer — a stakeholder, a new team member, someone from IRPA or
faculty governance, anyone who just wants to find something without reading
code. If you *are* a developer, start at [`README.md`](README.md) instead —
this page skips the technical detail on purpose.

## The one link that matters most

**The live tool:** https://d29yf6skp53yw4.cloudfront.net

That's it — that's the website. Open it, pick a major from the dropdown, and
you'll see real freshman course schedule options. For a full walkthrough of
what everything on that page means, see **[`USER_GUIDE.md`](USER_GUIDE.md)**.

(If that link ever stops working, it means the underlying cloud deployment
was rebuilt under a new address — ask a developer on the team to run the
lookup command in `README.md`'s "Deploying" section to get the current one.)

## If you're trying to do a specific thing

| I want to... | Go here |
|---|---|
| Use the tool to plan a freshman schedule | [`USER_GUIDE.md`](USER_GUIDE.md) |
| Understand *how* the recommendations are computed, and whether it's real data or a guess | [`USER_GUIDE.md`](USER_GUIDE.md) has this woven throughout; [`PROCESS_WRITEUP.md`](PROCESS_WRITEUP.md) has the full statistical methodology for the earlier historical-pattern approach |
| Understand the original problem this project was built to solve | [`challenge_overview.md`](challenge_overview.md) |
| Understand how the team scoped and made decisions during the build | [`contextv67/claude-starter-context.md`](contextv67/claude-starter-context.md) |
| Change how the tool works, or fix something technical | [`README.md`](README.md) — the technical entry point |
| Hand this project's methodology to another department (e.g. to build the same tool for Psychology) | [`PROCESS_WRITEUP.md`](PROCESS_WRITEUP.md), section 9 ("Reproduce the process for another major") |

## Plain-English glossary

You'll see these words in the other documents in this repo. Here's what they
mean without the jargon:

| Term | In plain English |
|---|---|
| **Repo** (repository) | The whole project folder, tracked by a tool called Git so every change is recorded and reversible. This GitHub page *is* the repo. |
| **Deploy / deployment** | The act of taking the code and actually turning it on in the cloud (AWS) so the public website works. Code sitting in the repo does nothing on its own until it's deployed. |
| **AWS** | Amazon Web Services — the cloud provider this project's live infrastructure runs on. Whenever you see "S3," "Lambda," "CloudFront," etc., those are all pieces of AWS. |
| **Lambda** | A small piece of backend code that runs only when needed (e.g. when someone asks the What-if advisor a question) — nothing is running (or costing money) when no one's using it. |
| **S3** | Amazon's file storage service. Used here to store the website's files and some precomputed data. |
| **CloudFront** | Makes the website fast and gives it a clean `https://` address, sitting in front of the S3 storage. |
| **API / API Gateway** | The "front door" that lets the website ask the backend a question (like "what if I fail this class?") and get an answer back. |
| **Bedrock** | Amazon's AI service — this is what generates the plain-language answers in the What-if advisor. It's given real, precomputed facts and asked to *explain* them, never to invent its own facts (see "compute first, LLM explains" in the README). |
| **LLM** | "Large language model" — the general term for AI models like the one behind Bedrock's answers. |
| **Artifact** | A generated file (JSON data) representing one major's set of real schedule options. Produced by `schedule_engine`, shown by the website. |
| **Roadmap** | The official term-by-term degree requirement map for a major — what a student needs to take and when, according to the catalog. |
| **Fit score** | A ranking number (not a percentage or grade) used to sort schedule options for the *same* major against each other — see `USER_GUIDE.md` for the full definition. |
| **Prerequisite** | A course that must be completed before another course can be taken. The What-if advisor checks the official catalog for these rather than guessing. |
| **IAM** | AWS's permission system — controls exactly which piece of code is allowed to touch which piece of AWS. Relevant mostly to developers; mentioned here so the word doesn't look scary in other docs. |

## A tour of the folders (non-technical version)

You don't need to open any of these to use the tool — this is just so the
repo doesn't feel like an unlabeled filing cabinet.

- **`advisor/`** — the code behind the What-if advisor box on the website.
- **`schedule_engine/`** — the code that generates the real, conflict-free
  schedule options you see on the website, from the actual course catalog.
- **`frontend/web/`** — the website itself (what your browser loads).
- **`api/`** and **`infra/`** — the behind-the-scenes plumbing that connects
  the website to AWS. Developer territory.
- **`mining/`**, **`bedrock/`**, **`frontend/app.py`** — an earlier version
  of this idea (a different, statistics-only approach) that's still in the
  repo and still works, but isn't what the live website uses today. Kept for
  reference and reproducibility — see `PROCESS_WRITEUP.md`.
- **`data/`** — real student/course data. This folder is intentionally
  **not** included when you download or view this repo on GitHub (it's
  "gitignored") — the underlying records never leave the machines that were
  explicitly given them, and every student ID in this project is randomized
  and non-reversible.
- **`contextv67/`**, **`challenge_overview.md`** — background on why this
  project exists and how the team scoped it during the original build.

## Common questions

**Is student data safe?**
Yes — every student identifier used anywhere in this project is randomly
assigned and cannot be reversed to identify a real person. Raw data files
are never stored in this public repo (see the `data/` note above).

**Does this replace an academic advisor?**
No. Every document in this repo says so explicitly — this is decision
support for department chairs and schedule builders, not a system that
enrolls students or makes final decisions. A human always reviews and
approves before anything becomes official.

**What if the website looks like it's not working?**
Check the banner at the top of the page — it tells you directly whether
you're looking at live or offline data, and if something's actually broken
it says so instead of silently showing wrong information. If it says
"offline/demo mode," the schedule data still works; only the What-if advisor
question box is affected.

**Who do I talk to about this project?**
This repo doesn't track a live staff directory — check with whoever shared
this link with you, or see `contextv67/claude-starter-context.md` for the
project's original stakeholders (IRPA as data owner, faculty-governance
partners, and the sponsoring department).
