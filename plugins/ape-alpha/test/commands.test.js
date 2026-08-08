import { readFile } from 'node:fs/promises';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { beforeAll, afterEach, describe, expect, it, vi } from 'vitest';
import { getRegistry } from '@agentrhq/webcmd/registry';

const here = path.dirname(fileURLToPath(import.meta.url));
const fixture = async (name) => JSON.parse(await readFile(path.join(here, 'fixtures', name), 'utf8'));

beforeAll(async () => {
  await import('../gdelt-news.js');
  await import('../google-news.js');
  await import('../yahoo-news.js');
  await import('../sec-filings.js');
  await import('../ir-latest.js');
});

describe('current news adapters', () => {
  it('normalizes and filters Google News RSS rows', async () => {
    const body = await readFile(path.join(here, 'fixtures', 'google-news.xml'), 'utf8');
    vi.stubGlobal('fetch', vi.fn(async () => new Response(body, { status: 200, headers: { 'content-type': 'application/rss+xml' } })));
    const definition = command('google-news');
    const rows = await definition.func({ query: 'Palantir Technologies Inc.', ticker: 'PLTR', language: 'en-US', country: 'US', ceid: 'US:en', limit: 10 });
    expect(rows).toHaveLength(1);
    expect(Object.keys(rows[0])).toEqual(definition.columns);
    expect(rows[0].provider).toBe('google-news');
    expect(rows[0].title).toContain('Palantir');
  });

  it('keeps only Yahoo stories related to the resolved ticker', async () => {
    const body = await fixture('yahoo-news.json');
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })));
    const definition = command('yahoo-news');
    const rows = await definition.func({ query: 'Palantir Technologies Inc.', ticker: 'PLTR', limit: 10 });
    expect(rows).toHaveLength(1);
    expect(Object.keys(rows[0])).toEqual(definition.columns);
    expect(rows[0].provider).toBe('yahoo-news');
    expect(rows[0].title).toContain('Palantir');
  });
});

afterEach(() => vi.unstubAllGlobals());

function command(name) {
  const result = getRegistry().get(`ape-alpha/${name}`);
  if (!result) throw new Error(`Command ${name} not registered`);
  return result;
}

function expectAligned(commandDefinition, row) {
  expect(Object.keys(row)).toEqual(commandDefinition.columns);
  expect(row.sourceUrl).toMatch(/^https:\/\//);
  expect(row.rawContentHash).toMatch(/^[a-f0-9]{40,64}$|^\d{64}$/);
  expect(Number.isNaN(Date.parse(row.sourceCreatedAt))).toBe(false);
}

describe('APE Alpha WebCMD contracts', () => {
  it('normalizes GDELT articles into SourceEvent columns', async () => {
    const body = await fixture('gdelt.json');
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })));
    const definition = command('gdelt-news');
    const rows = await definition.func({ query: 'Apple Inc', ticker: 'AAPL', timespan: '7d', limit: 1 });
    expect(rows).toHaveLength(1);
    expectAligned(definition, rows[0]);
    expect(rows[0].sourceType).toBe('news');
  });

  it('normalizes official SEC filings into SourceEvent columns', async () => {
    const body = await fixture('sec.json');
    vi.stubGlobal('fetch', vi.fn(async () => new Response(JSON.stringify(body), { status: 200, headers: { 'content-type': 'application/json' } })));
    const definition = command('sec-filings');
    const rows = await definition.func({ cik: '320193', ticker: 'AAPL', form: '8-K', limit: 1 });
    expect(rows).toHaveLength(1);
    expectAligned(definition, rows[0]);
    expect(rows[0].sourceType).toBe('filing');
  });

  it('keeps browser IR extraction column-aligned', async () => {
    const extracted = await fixture('ir.json');
    const page = { goto: vi.fn(async () => undefined), evaluate: vi.fn(async () => extracted) };
    const definition = command('ir-latest');
    const rows = await definition.func(page, { url: 'https://investors.example.com/news', ticker: 'ASTS', limit: 10 });
    expect(page.goto).toHaveBeenCalledOnce();
    expectAligned(definition, rows[0]);
    expect(rows[0].sourceType).toBe('ir');
  });
});
