import { cli, Strategy } from '@agentrhq/webcmd/registry';
import {
  ArgumentError,
  CommandExecutionError,
  EmptyResultError,
} from '@agentrhq/webcmd/errors';

async function sha256(value) {
  const bytes = new TextEncoder().encode(value);
  const digest = await globalThis.crypto.subtle.digest('SHA-256', bytes);
  return Array.from(new Uint8Array(digest), (byte) => byte.toString(16).padStart(2, '0')).join('');
}

cli({
  site: 'ape-alpha',
  name: 'sec-filings',
  tags: ['search'],
  keywords: ['edgar', 'catalyst', '8-k'],
  access: 'read',
  description: 'Read point-in-time SEC filing history for a company CIK',
  domain: 'data.sec.gov',
  strategy: Strategy.PUBLIC,
  browser: false,
  args: [
    { name: 'cik', type: 'string', required: true, positional: true, help: 'SEC CIK with or without leading zeroes' },
    { name: 'ticker', type: 'string', required: true, help: 'Resolved US ticker' },
    { name: 'form', type: 'string', default: '8-K', help: 'Form filter, or ALL' },
    { name: 'limit', type: 'int', default: 20, help: 'Number of filings (1-100)' },
  ],
  columns: [
    'eventId', 'sourceType', 'ticker', 'title', 'sourceUrl',
    'sourceCreatedAt', 'sourceFirstSeenAt', 'ingestedAt',
    'tickerConfidence', 'rawContentHash', 'metadata',
  ],
  func: async (args) => {
    const cikInput = String(args.cik || '').trim();
    const ticker = String(args.ticker || '').trim().toUpperCase();
    const formFilter = String(args.form || '').trim().toUpperCase();
    const limit = Number(args.limit);
    if (!/^\d{1,10}$/.test(cikInput)) throw new ArgumentError('cik must contain 1 to 10 digits');
    if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(ticker)) throw new ArgumentError('ticker must be a valid US symbol');
    if (!formFilter) throw new ArgumentError('form is required');
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
      throw new ArgumentError('limit must be an integer from 1 to 100');
    }
    const cik = cikInput.padStart(10, '0');
    const userAgent = process.env.SEC_USER_AGENT || 'APE Alpha research contact@example.com';
    const response = await fetch(`https://data.sec.gov/submissions/CIK${cik}.json`, {
      headers: { Accept: 'application/json', 'User-Agent': userAgent },
    });
    if (!response.ok) throw new CommandExecutionError(`SEC returned HTTP ${response.status}`);
    const body = await response.json();
    const recent = body?.filings?.recent;
    if (!recent || !Array.isArray(recent.accessionNumber)) {
      throw new CommandExecutionError('SEC response is missing recent filings');
    }

    const ingestedAt = new Date().toISOString();
    const rows = [];
    for (let index = 0; index < recent.accessionNumber.length && rows.length < limit; index += 1) {
      const form = String(recent.form[index] || '').toUpperCase();
      if (formFilter !== 'ALL' && form !== formFilter) continue;
      const accession = String(recent.accessionNumber[index]);
      const accessionPath = accession.replaceAll('-', '');
      const primaryDocument = String(recent.primaryDocument[index] || '');
      const sourceUrl = `https://www.sec.gov/Archives/edgar/data/${Number(cik)}/${accessionPath}/${primaryDocument}`;
      const accepted = String(recent.acceptanceDateTime?.[index] || recent.filingDate[index]);
      const sourceCreatedAt = accepted.includes('T') ? `${accepted.replace(/Z$/, '')}Z` : `${accepted}T00:00:00Z`;
      const rawContentHash = await sha256(`${accession}|${form}|${sourceCreatedAt}`);
      rows.push({
        eventId: `sec_${accessionPath}`,
        sourceType: 'filing',
        ticker,
        title: `${form} — ${body.name}`,
        sourceUrl,
        sourceCreatedAt,
        sourceFirstSeenAt: sourceCreatedAt,
        ingestedAt,
        tickerConfidence: 1,
        rawContentHash,
        metadata: JSON.stringify({ accession, form, filingDate: recent.filingDate[index], reportDate: recent.reportDate[index] || null }),
      });
    }
    if (rows.length === 0) throw new EmptyResultError(`No ${formFilter} filings for CIK ${cik}`);
    return rows;
  },
});
