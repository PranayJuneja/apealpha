import { cli, Strategy } from '@agentrhq/webcmd/registry';
import { ArgumentError, CommandExecutionError } from '@agentrhq/webcmd/errors';

function decodeXml(value) {
  return String(value || '')
    .replace(/^<!\[CDATA\[|\]\]>$/g, '')
    .replace(/&amp;/g, '&')
    .replace(/&quot;/g, '"')
    .replace(/&#39;|&apos;/g, "'")
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .trim();
}

function tag(block, name) {
  const match = block.match(new RegExp(`<${name}(?:\\s[^>]*)?>([\\s\\S]*?)<\\/${name}>`, 'i'));
  return decodeXml(match?.[1]);
}

function cleanTitle(raw) {
  const match = String(raw || '').match(/^(.*?)\s+-\s+([^-]+)$/);
  return match ? [match[1].trim(), match[2].trim()] : [String(raw || '').trim(), ''];
}

function companyTerm(company) {
  return String(company || '')
    .replace(/\b(incorporated|inc|corp(?:oration)?|company|co|limited|ltd|plc|technologies)\b\.?/gi, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function matchesSecurity(title, ticker, company) {
  const tickerPattern = new RegExp(`(^|[^A-Za-z0-9])\\$?${ticker.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}([^A-Za-z0-9]|$)`, 'i');
  const root = companyTerm(company);
  const companyMatch = root.length >= 3 && title.toLowerCase().includes(root.toLowerCase());
  const marketContext = /\b(stock|share|market|invest|analyst|earnings|revenue|contract|defen[cs]e|company|business|valuation|price|nasdaq|nyse)\w*\b/i.test(title);
  return tickerPattern.test(title) || (companyMatch && marketContext);
}

export function parseGoogleNews(xml, { ticker, company, language, country, limit }) {
  const rows = [];
  for (const match of String(xml || '').matchAll(/<item>([\s\S]*?)<\/item>/gi)) {
    const block = match[1];
    const link = tag(block, 'link');
    const createdAt = new Date(tag(block, 'pubDate'));
    const [title, titlePublisher] = cleanTitle(tag(block, 'title'));
    const publisher = tag(block, 'source') || titlePublisher;
    if (!title || !/^https:\/\//i.test(link) || Number.isNaN(createdAt.valueOf())) continue;
    if (!matchesSecurity(title, ticker, company)) continue;
    rows.push({
      title,
      url: link,
      publisher,
      createdAt: createdAt.toISOString(),
      language,
      country,
      provider: 'google-news',
    });
    if (rows.length >= limit) break;
  }
  return rows;
}

cli({
  site: 'ape-alpha',
  name: 'google-news',
  tags: ['search'],
  keywords: ['current news', 'headlines', 'ticker news'],
  access: 'read',
  description: 'Search current locale-aware Google News coverage for a listed security',
  domain: 'news.google.com',
  strategy: Strategy.PUBLIC,
  browser: false,
  args: [
    { name: 'query', type: 'string', required: true, positional: true, help: 'Resolved company name' },
    { name: 'ticker', type: 'string', required: true, help: 'Resolved ticker' },
    { name: 'language', type: 'string', default: 'en-US', help: 'Google News language code' },
    { name: 'country', type: 'string', default: 'US', help: 'Google News country code' },
    { name: 'ceid', type: 'string', default: 'US:en', help: 'Google News edition identifier' },
    { name: 'limit', type: 'int', default: 100, help: 'Maximum matching articles (1-100)' },
  ],
  columns: ['title', 'url', 'publisher', 'createdAt', 'language', 'country', 'provider'],
  func: async (args) => {
    const company = String(args.query || '').trim();
    const ticker = String(args.ticker || '').trim().toUpperCase();
    const language = String(args.language || '').trim();
    const country = String(args.country || '').trim().toUpperCase();
    const ceid = String(args.ceid || '').trim();
    const limit = Number(args.limit);
    if (!company) throw new ArgumentError('query is required');
    if (!/^[A-Z][A-Z0-9.-]{0,14}$/.test(ticker)) throw new ArgumentError('ticker is invalid');
    if (!Number.isInteger(limit) || limit < 1 || limit > 100) {
      throw new ArgumentError('limit must be an integer from 1 to 100');
    }
    const endpoint = new URL('https://news.google.com/rss/search');
    endpoint.searchParams.set('q', `"${companyTerm(company) || company}" stock OR ${ticker}`);
    endpoint.searchParams.set('hl', language);
    endpoint.searchParams.set('gl', country);
    endpoint.searchParams.set('ceid', ceid);
    const response = await fetch(endpoint, {
      headers: { Accept: 'application/rss+xml', 'User-Agent': 'Mozilla/5.0 (compatible; ape-alpha/0.2)' },
    });
    if (!response.ok) throw new CommandExecutionError(`Google News returned HTTP ${response.status}`);
    const body = await response.text();
    if (!/<rss\b/i.test(body)) throw new CommandExecutionError('Google News returned non-RSS content');
    return parseGoogleNews(body, { ticker, company, language, country, limit });
  },
});
