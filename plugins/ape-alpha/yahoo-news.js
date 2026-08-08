import { cli, Strategy } from '@agentrhq/webcmd/registry';
import { ArgumentError, CommandExecutionError } from '@agentrhq/webcmd/errors';

function companyTerm(company) {
  return String(company || '')
    .replace(/\b(incorporated|inc|corp(?:oration)?|company|co|limited|ltd|plc|technologies)\b\.?/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function titleMatches(title, ticker, company) {
  const escaped = ticker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
  const tickerPattern = new RegExp(`(^|[^A-Za-z0-9])\\$?${escaped}([^A-Za-z0-9]|$)`, 'i');
  const root = companyTerm(company);
  return tickerPattern.test(title) || (root.length >= 3 && title.toLowerCase().includes(root.toLowerCase()));
}

export function parseYahooNews(payload, { ticker, company, limit }) {
  if (!payload || !Array.isArray(payload.news)) {
    throw new CommandExecutionError('Yahoo Finance response is missing news rows');
  }
  const rows = [];
  for (const item of payload.news) {
    const title = String(item?.title || '').trim();
    const url = String(item?.link || '').trim();
    const createdAt = new Date(Number(item?.providerPublishTime || 0) * 1000);
    if (item?.type !== 'STORY' || !title || !/^https:\/\//i.test(url) || Number.isNaN(createdAt.valueOf())) continue;
    // Yahoo's relatedTickers list is intentionally broad and includes symbols
    // merely mentioned inside general market roundups. The visible headline is
    // our evidence contract, so hidden association alone never counts a story.
    if (!titleMatches(title, ticker, company)) continue;
    rows.push({
      title,
      url,
      publisher: String(item?.publisher || 'Yahoo Finance').trim(),
      createdAt: createdAt.toISOString(),
      language: 'en-US',
      country: 'US',
      provider: 'yahoo-news',
    });
    if (rows.length >= limit) break;
  }
  return rows;
}

cli({
  site: 'ape-alpha',
  name: 'yahoo-news',
  tags: ['search'],
  keywords: ['Yahoo Finance', 'current news', 'ticker headlines'],
  access: 'read',
  description: 'Search current Yahoo Finance news for a listed security',
  domain: 'query1.finance.yahoo.com',
  strategy: Strategy.PUBLIC,
  browser: false,
  args: [
    { name: 'query', type: 'string', required: true, positional: true, help: 'Resolved company name' },
    { name: 'ticker', type: 'string', required: true, help: 'Resolved ticker' },
    { name: 'limit', type: 'int', default: 50, help: 'Maximum matching articles (1-100)' },
  ],
  columns: ['title', 'url', 'publisher', 'createdAt', 'language', 'country', 'provider'],
  func: async (args) => {
    const company = String(args.query || '').trim();
    const ticker = String(args.ticker || '').trim().toUpperCase();
    const limit = Number(args.limit);
    if (!company) throw new ArgumentError('query is required');
    if (!/^[A-Z][A-Z0-9.-]{0,14}$/.test(ticker)) throw new ArgumentError('ticker is invalid');
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
      throw new ArgumentError('limit must be an integer from 1 to 100');
    }
    const endpoint = new URL('https://query1.finance.yahoo.com/v1/finance/search');
    // Yahoo's search rejects some otherwise valid `company + ticker` strings
    // with an empty news array. Discover by company, then enforce ticker or
    // company relevance on every returned row below.
    endpoint.searchParams.set('q', companyTerm(company) || company);
    endpoint.searchParams.set('quotesCount', '0');
    endpoint.searchParams.set('newsCount', String(Math.min(100, Math.max(limit * 2, 20))));
    endpoint.searchParams.set('enableFuzzyQuery', 'false');
    endpoint.searchParams.set('enableEnhancedTrivialQuery', 'true');
    const response = await fetch(endpoint, {
      headers: { Accept: 'application/json', 'User-Agent': 'Mozilla/5.0 (compatible; ape-alpha/0.2)' },
    });
    if (!response.ok) throw new CommandExecutionError(`Yahoo Finance returned HTTP ${response.status}`);
    const contentType = response.headers.get('content-type') || '';
    if (!contentType.includes('json')) throw new CommandExecutionError('Yahoo Finance returned non-JSON content');
    return parseYahooNews(await response.json(), { ticker, company, limit });
  },
});
