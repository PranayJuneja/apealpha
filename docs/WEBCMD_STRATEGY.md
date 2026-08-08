# WebCMD acquisition strategies

APE Alpha treats WebCMD as the acquisition control plane. Every acquisition
command returns deterministic, column-aligned JSON that can be normalized into
`SourceEvent` records.

## GDELT news timeline

Strategy: `PUBLIC_API`

Contract: stable public HTTP interface

Evidence:

- Endpoint: `https://api.gdeltproject.org/api/v2/doc/doc`
- Authentication: none
- Expected replay: JSON timeline or article records for a company query

Why not browser state: GDELT publishes a documented public API, so browser DOM
or undocumented page requests would add unnecessary drift.

## SEC filing history

Strategy: `PUBLIC_API`

Contract: stable official government JSON interface

Evidence:

- Endpoint: `https://data.sec.gov/submissions/CIK##########.json`
- Authentication: none; a descriptive User-Agent is required
- Expected replay: filing accession numbers, forms, acceptance timestamps and
  primary document paths

Why not browser state: the SEC explicitly publishes the submissions endpoint.

## Company investor-relations page

Strategy: `DOM_STATE`

Contract: visible UI

Evidence:

- Target: a caller-supplied public investor-relations URL
- Authentication: none
- Expected replay: visible release links and publication dates anchored by
  headings, `time` elements and article links

Why not a public API: company IR systems vary and frequently expose no common
documented interface. The visible releases list is the cross-site contract.
Selector drift and unsupported page shapes raise typed execution errors.

Browser verification is intentionally separated from public-adapter validation.
The current host is Windows ARM64, which WebCMD 0.5.3 reports as unsupported for
browser connectivity. Run `ir-latest` verification on a supported x64 Windows,
Linux or macOS runner.
