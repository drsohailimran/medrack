# P2 overnight policy

## Failure handling

**If one book fails → skip it and continue with the next.**

Failures include:
- Hybrid OCR error / timeout
- Zero chunks / empty text
- Post-ingest **verification** hard-fail
- Missing file for an ORDER line

Failed books are recorded in `p2-report.md` / `p2-report.json` for a later retry.

## Do not start until owner says so

- Owner will provide PDFs + order **tonight**
- Start only after: files in this folder + `ORDER.md` + message **“P2 ready”** / **“start P2”**

## Success path per book

1. Hybrid OCR (Auto Marker on by default)
2. Index into Chroma
3. Automatic verification (manifest + Chroma count + sample retrieval)
4. Only then mark book **OK** and move PDF to `done/`

## Defaults

| Setting | Value |
|---------|--------|
| Hybrid OCR | on |
| Auto Marker | on |
| Replace existing | on (re-ingest same PDF if re-run) |
| On failure | **skip → next** |
| On missing file | skip → next |
