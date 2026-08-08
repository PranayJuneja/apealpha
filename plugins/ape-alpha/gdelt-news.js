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

function toIso(value) {
  const text = String(value || '');
  const match = text.match(/^(\d{4})(\d{2})(\d{2})T(\d{2})(\d{2})(\d{2})Z$/);
  return match
    ? `${match[1]}-${match[2]}-${match[3]}T${match[4]}:${match[5]}:${match[6]}Z`
    : new Date(text).toISOString();
}

cli({
  site: 'ape-alpha',
  name: 'gdelt-news',
  tags: ['search'],
  keywords: ['catalyst', 'historical news', 'narrative'],
  access: 'read',
  description: 'Search GDELT for point-in-time company news events',
  domain: 'api.gdeltproject.org',
  strategy: Strategy.PUBLIC,
  browser: false,
  args: [
    { name: 'query', type: 'string', required: true, positional: true, help: 'Company name or catalyst query' },
    { name: 'ticker', type: 'string', required: true, help: 'Resolved US ticker' },
    { name: 'timespan', type: 'string', default: '3m', help: 'GDELT timespan such as 24h, 7d, 1w or 3m' },
    { name: 'limit', type: 'int', default: 25, help: 'Number of articles (1-250)' },
  ],
  columns: [
    'eventId', 'sourceType', 'ticker', 'title', 'sourceUrl',
    'sourceCreatedAt', 'sourceFirstSeenAt', 'ingestedAt',
    'tickerConfidence', 'rawContentHash', 'metadata',
  ],
  func: async (args) => {
    const query = String(args.query || '').trim();
    const ticker = String(args.ticker || '').trim().toUpperCase();
    const timespan = String(args.timespan || '').trim();
    const limit = Number(args.limit);
    if (!query) throw new ArgumentError('query is required');
    if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(ticker)) throw new ArgumentError('ticker must be a valid US symbol');
    // GDELT's grammar is min|h|d|w|m. It ignores anything else rather than
    // rejecting it, silently returning its own short default window, so an
    // invalid unit has to be caught here.
    if (!/^[0-9]+(?:min|h|d|w|m)$/.test(timespan)) {
      throw new ArgumentError('timespan must look like 24h, 7d, 1w or 3m');
    }
    if (!Number.isInteger(limit) || limit < 1 || limit > 250) {
      throw new ArgumentError('limit must be an integer from 1 to 250');
    }

    const endpoint = new URL('https://api.gdeltproject.org/api/v2/doc/doc');
    endpoint.searchParams.set('query', query);
    endpoint.searchParams.set('mode', 'artlist');
    endpoint.searchParams.set('format', 'json');
    endpoint.searchParams.set('sort', 'datedesc');
    endpoint.searchParams.set('timespan', timespan);
    endpoint.searchParams.set('maxrecords', String(limit));
    const response = await fetch(endpoint, { headers: { Accept: 'application/json' } });
    if (!response.ok) throw new CommandExecutionError(`GDELT returned HTTP ${response.status}`);
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('json')) throw new CommandExecutionError('GDELT returned non-JSON content');
    const body = await response.json();
    if (!Array.isArray(body.articles)) throw new CommandExecutionError('GDELT response is missing articles');
    if (body.articles.length === 0) throw new EmptyResultError(`No GDELT articles for ${query}`);

    const ingestedAt = new Date().toISOString();
    return Promise.all(body.articles.map(async (article) => {
      const sourceUrl = String(article.url || '');
      const sourceCreatedAt = toIso(article.seendate);
      const rawContentHash = await sha256(`${sourceUrl}|${article.title || ''}|${sourceCreatedAt}`);
      return {
        eventId: `gdelt_${rawContentHash.slice(0, 20)}`,
        sourceType: 'news',
        ticker,
        title: String(article.title || '').trim(),
        sourceUrl,
        sourceCreatedAt,
        sourceFirstSeenAt: sourceCreatedAt,
        ingestedAt,
        tickerConfidence: 1,
        rawContentHash,
        metadata: JSON.stringify({
          domain: article.domain || null,
          language: article.language || null,
          sourceCountry: article.sourcecountry || null,
          image: article.socialimage || null,
        }),
      };
    }));
  },
});
