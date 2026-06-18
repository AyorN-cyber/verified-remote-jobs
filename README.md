# Verified Global Remote Jobs Pipeline

This project discovers and verifies remote job prospects for candidates in any region. It is designed to reject stale, fake, paywalled, region-restricted, or misleading listings before they reach the candidate.

## Safety Rule

Job boards are discovery sources, not proof. A lead is only approved when the pipeline can verify recency, official source, apply-link behavior, country/global eligibility, and scam-risk signals.

## Setup

1. Create a virtual environment.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Use the virtual environment when running the pipeline. This avoids warnings caused by incompatible packages in a global Python installation.

2. Add local API keys.

Copy `.env.example` to `.env.local`, then fill in local values. Never commit `.env.local`.

```env
AI_PROVIDER=claude
ANTHROPIC_API_KEY=your_claude_key
SERPAPI_API_KEY=your_serpapi_key
```

The pipeline works without AI keys, but Claude improves extraction of eligibility evidence, candidate fit, and outreach strategy.

Configure the candidate's location and target regions for each run:

```env
CANDIDATE_NAME=Sample Candidate
CANDIDATE_LOCATION=Remote
CANDIDATE_COUNTRY=
TARGET_WORK_REGIONS=Worldwide
TARGET_ROLES=customer support,customer success,crm specialist,virtual assistant,operations assistant,sales support
CANDIDATE_STRENGTHS=customer support,CRM hygiene,email phone and chat support,client follow-up,calendar and admin coordination,remote work discipline
```

## Run

```powershell
python verified_jobs_pipeline.py --limit 25
```

For faster verifier debugging without Claude enrichment:

```powershell
python verified_jobs_pipeline.py --limit 25 --no-ai
```

Company watchlist review is available, but watchlist pages cannot become approved job prospects by themselves:

```powershell
python verified_jobs_pipeline.py --limit 25 --include-watchlist
```

Outputs are written to:

```text
verified_pipeline_output/
```

The output files are:

- `verified_job_prospects.csv`
- `verified_job_prospects.xlsx`
- `verified_job_prospects_report.docx`

## Tests

Run offline tests without spending API credits:

```powershell
python -m unittest discover -s tests
```

## Verification Gates

Each lead is checked for:

- posting freshness within `FRESHNESS_HOURS`, default `10`
- official ATS or company-domain evidence
- apply link opens successfully and does not remain trapped on a job-board page
- candidate-region/global eligibility language
- region restrictions such as US-only, Canada-only, UK-only, EU-only, work-authorization-only, hybrid, or onsite
- scam signals such as payment requests, fake checks, crypto, OTP, BVN, forced Telegram/WhatsApp-only process, or equipment purchase

Only `approved` prospects should be sent to the candidate. `manual_review` leads require a human check. `rejected` leads are kept for audit.

For third-party boards, the verifier parses the job page for explicit apply links, follows redirects, and prefers trusted ATS or company-domain targets. Board-only apply paths are rejected until an official application route is found.

The public project is region-agnostic. Set `CANDIDATE_COUNTRY` and `TARGET_WORK_REGIONS` for your own use case.

## Source Lanes

The pipeline currently supports:

- RemoteOK API
- Remotive API
- Jobicy API
- We Work Remotely RSS
- SerpAPI Google Jobs, when configured
- SerpAPI targeted search, when configured
- company watchlist review

The source list is intentionally broad but conservative. More official ATS connectors can be added under `job_pipeline/sources.py`.

## AI Usage

AI is optional and should not be treated as proof that a job is genuine. The deterministic verifier checks links, timestamps, source domains, eligibility language, and scam patterns first. Claude is used only to extract and summarize evidence from the job text.

When Claude is configured, it also structures candidate-facing output:

- why the role fits the candidate
- application strategy
- LinkedIn outreach message
- email follow-up message
- materials to prepare
- company research notes
- concise verification summary

The CSV/XLSX place these fields first, followed by the audit fields. The DOCX report groups approved, manual-review, and rejected roles separately.

## Publishing Notes

Before publishing this project:

- keep `.env.local` private
- do not commit API keys
- remove old generated reports if they contain unverified leads
- include a clear disclaimer that users must still review final applications manually
