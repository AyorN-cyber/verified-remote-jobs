# Public Release Checklist

Use this before pushing the project to a public GitHub repository.

## Files To Keep Public

- source code under `job_pipeline/`
- tests under `tests/`
- `README.md`
- `requirements.txt`
- `.env.example`
- `.gitignore`
- `SECURITY.md`
- documentation under `docs/`

## Files To Keep Private

- `.env`
- `.env.local`
- CVs and resumes
- generated candidate reports
- generated CSV/XLSX/DOCX prospect packs
- screenshots containing account details
- API responses that include personal data
- old manually generated job packs

## Before First Public Commit

1. Run `python -m unittest discover -s tests`.
2. Confirm `.env.local` is ignored.
3. Confirm private CV folders and generated outputs are ignored.
4. Run a secret scan with a tool such as Gitleaks or GitHub secret scanning.
5. Create a fresh public repository instead of publishing this whole working folder if private files were ever committed.
6. Add screenshots only after redacting keys, personal emails, account IDs, and candidate details.
7. Keep sample outputs synthetic. Do not use a real candidate CV or real private search history as demo data.
8. Keep candidate-specific defaults out of the public repo. Use `.env.local` for local runs.

## Recommended Repository Shape

```text
verified-remote-jobs/
  job_pipeline/
  tests/
  docs/
  examples/
    sample_input.json
    sample_output.csv
  .env.example
  .gitignore
  README.md
  SECURITY.md
  requirements.txt
```
