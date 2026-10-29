# Hackathon compliance

**Event:** Nebius × NVIDIA Global AI Hackathon 2026
**Official page:** <https://nebiusglobalaihackathon.devpost.com/>
**Note:** the link in the original brief (`obalaihackathon.devpost.com`) did not load. The official page is the one above.

## What was actually read

| Source | How verified |
|---|---|
| Official Rules (`/rules`) | Fetched and read directly. Primary authority. |
| FAQs (`/details/faqs`) | Fetched and read directly. |
| Overview and Resources tabs | **Not read.** The overview page was not fetched; re-check both before submitting. |
| Nebius model ids and base URL | Secondary sources only (Nebius marketing page, Mastra and Agno docs, community repos). **Not yet confirmed against the official Nebius API reference or a live key.** Confirm with `GET /v1/models`. |
| Nemotron license terms | Not verified from NVIDIA. Read the model card before submitting. |

Rules can change. If anything conflicts, the Official Rules win. Re-read them before final submission.

## Deadline

**Friday 30 Oct 2026, 10:00 AM PDT = 22:30 IST** (17:00 UTC). Submissions cannot be edited after that. Do not plan to submit in the last hour.

## Requirements and Cygnus status

| # | Requirement (source: Official Rules unless noted) | Cygnus status |
|---|---|---|
| 1 | Working software app that **runs on Nebius Token Factory or Nebius AI Cloud**. Defined as: a runtime call to the Token Factory inference API, **or** deployed on Nebius AI Cloud compute (Serverless Jobs, Serverless Endpoints, DevPods) | Client written (`backend/app/ai/nebius.py`). **Not yet proven with a real call** (no key in this environment). |
| 2 | Uses **at least one NVIDIA open-source model** (e.g. Nemotron) | Configured to `nvidia/nemotron-3-super-120b-a12b` (unverified id). |
| 3 | Fits one of four tracks | Chosen: **Best Apps and Agents**. |
| 4 | NVIDIA model must come **through Nebius**. HuggingFace/OpenRouter do not count (FAQ) | Compliant by design. |
| 5 | Public code repo (GitHub/GitLab/Bitbucket) with all source and instructions | Local repo only. **Needs publishing.** |
| 6 | Repo has an **open-source license file** visible in the repo About section | `LICENSE` (MIT) added. Confirm GitHub detects it. |
| 7 | README with setup and run instructions that **highlights how Nemotron/other NVIDIA models and Token Factory are used** | Setup done. The NVIDIA/Nebius usage section must be added once the agent exists. |
| 8 | **URL to a working demo / hosted app / test build**, free and unrestricted for judges until judging ends (15 Dec). Private sites must include login credentials | **Not done.** Needs deployment. |
| 9 | Text description of features and functionality | Not done. |
| 10 | **Demo video under 3 min**, public on **YouTube**, showing the project functioning, no third-party trademarks or copyrighted music | Not done. |
| 11 | Identify the track on the submission form | Decided, not submitted. |
| 12 | **Provide feedback** on Nebius Token Factory / AI Cloud and NVIDIA tools (required field; also eligible for the Most Valuable Feedback prize) | Not done. Keep notes while building. |
| 13 | If the project existed before 26 Aug 2026, explain what was significantly updated | Cygnus is new. Not applicable. |
| 14 | Third-party APIs/SDKs: must be authorized to use them | Only OSS libraries so far. |
| 15 | Original work, solely owned by entrant; English materials | OK. |

## Judging (four equally weighted criteria)

1. **Technological Implementation**: how well it is built and how effectively it uses Token Factory/AI Cloud and Nemotron.
2. **Design**: a complete, coherent product experience, not a proof of concept.
3. **Potential Impact**: credible, specific case for a real problem and audience.
4. **Quality of the Idea**: creative, non-obvious use of the models; real understanding of the problem.

Stage 1 is pass/fail: the project must genuinely fit the track and genuinely use the required APIs.

## Prizes relevant to Cygnus

- Overall: $20k / $10k / $6k. A project is eligible for **one Overall or one Track award, plus one Bonus award**.
- **Best Use of Tavily ($3,000)**: needs a *functional runtime call to the Tavily API*. A natural fit: looking up a retailer's published return policy. Optional; decide in Part 2.
- **Most Valuable Feedback ($100 + swag, 10 winners)**: just complete the feedback section well.

## Access and credits

- Credits are **Token Factory** credits. Official FAQ mentions the credits-form code `NEBIUS-DEVPOST-GLOBAL26` and the Nebius Builder Program (<https://dev.nebius.com/builders>).
- **Risk to check today:** the FAQ says some countries are missing from Nebius's Token Factory billing/country list. This is not a hackathon eligibility rule (India is not in the rules' excluded list), but you must confirm that you can create a key. If you cannot, ask on the Nebius Discord (link in the FAQ page) immediately.
- Residents of Brazil, Quebec, Russia, Crimea, Cuba, Iran, North Korea and other OFAC-sanctioned places are excluded.

## Pre-submission checklist

- [ ] Token Factory key works; `scripts/check_llm.py` passes with a real NVIDIA model
- [ ] Repo public, MIT license detected, README has NVIDIA/Nebius section
- [ ] Hosted demo URL works in an incognito window, no login or paywall
- [ ] Video < 3:00, public on YouTube, shows the app working, no copyrighted music
- [ ] Description, track, and feedback fields filled
- [ ] Simulated actions labelled in UI, video and description
- [ ] Submitted **at least a few hours before** 22:30 IST on 30 Oct
