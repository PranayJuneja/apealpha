import { cli, Strategy } from '@agentrhq/webcmd/registry';
import {
  ArgumentError,
  CommandExecutionError,
  EmptyResultError,
} from '@agentrhq/webcmd/errors';

cli({
  site: 'ape-alpha',
  name: 'ir-latest',
  tags: ['search'],
  keywords: ['investor relations', 'press releases', 'catalyst'],
  access: 'read',
  description: 'Extract the latest visible releases from a company IR page',
  domain: '*',
  // WebCMD 0.5.3 represents visible DOM-state commands with the UI strategy.
  strategy: Strategy.UI,
  browser: true,
  args: [
    { name: 'url', type: 'string', required: true, positional: true, help: 'Public investor-relations page URL' },
    { name: 'ticker', type: 'string', required: true, help: 'Resolved US ticker' },
    { name: 'limit', type: 'int', default: 10, help: 'Number of visible releases (1-50)' },
  ],
  columns: [
    'eventId', 'sourceType', 'ticker', 'title', 'sourceUrl',
    'sourceCreatedAt', 'sourceFirstSeenAt', 'ingestedAt',
    'tickerConfidence', 'rawContentHash', 'metadata',
  ],
  func: async (page, args) => {
    const url = String(args.url || '').trim();
    const ticker = String(args.ticker || '').trim().toUpperCase();
    const limit = Number(args.limit);
    let parsed;
    try { parsed = new URL(url); } catch { throw new ArgumentError('url must be a valid http or https URL'); }
    if (!['http:', 'https:'].includes(parsed.protocol)) throw new ArgumentError('url must be a valid http or https URL');
    if (!/^[A-Z][A-Z0-9.-]{0,9}$/.test(ticker)) throw new ArgumentError('ticker must be a valid US symbol');
    if (!Number.isInteger(limit) || limit < 1 || limit > 50) throw new ArgumentError('limit must be an integer from 1 to 50');

    await page.goto(url);
    const rows = await page.evaluate(`(async () => {
      const ticker = ${JSON.stringify(ticker)};
      const limit = ${JSON.stringify(limit)};
      const ingestedAt = new Date().toISOString();
      const seen = new Set();
      const candidates = [];
      const anchors = Array.from(document.querySelectorAll('article a[href], main a[href], [class*="release"] a[href], [class*="news"] a[href]'));
      for (const anchor of anchors) {
        const title = (anchor.textContent || '').replace(/\\s+/g, ' ').trim();
        if (title.length < 12 || title.length > 300) continue;
        const sourceUrl = new URL(anchor.href, location.href).href;
        if (seen.has(sourceUrl)) continue;
        const container = anchor.closest('article, li, div') || anchor.parentElement;
        const time = container?.querySelector('time');
        const dateText = time?.getAttribute('datetime') || time?.textContent?.trim() || '';
        const parsedDate = Date.parse(dateText);
        const sourceCreatedAt = Number.isNaN(parsedDate) ? ingestedAt : new Date(parsedDate).toISOString();
        const bytes = new TextEncoder().encode(sourceUrl + '|' + title + '|' + sourceCreatedAt);
        const digest = await crypto.subtle.digest('SHA-256', bytes);
        const rawContentHash = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
        seen.add(sourceUrl);
        candidates.push({
          eventId: 'ir_' + rawContentHash.slice(0, 20), sourceType: 'ir', ticker, title,
          sourceUrl, sourceCreatedAt, sourceFirstSeenAt: ingestedAt, ingestedAt,
          tickerConfidence: 1, rawContentHash,
          metadata: JSON.stringify({ visibleDate: dateText || null, host: location.host }),
        });
        if (candidates.length >= limit) break;
      }
      return candidates;
    })()`);
    if (!Array.isArray(rows)) throw new CommandExecutionError('IR page parser returned an unsupported shape');
    if (rows.length === 0) throw new EmptyResultError('No visible release links found on the IR page');
    return rows;
  },
});
