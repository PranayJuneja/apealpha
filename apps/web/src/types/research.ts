export type Phase = "WHISPER" | "CONFIRMED" | "MANIA" | "EXIT_LIQUIDITY" | "INDETERMINATE";

export type SourceKind = "social" | "news" | "filing" | "ir" | "market";

export type SourceEvent = {
  event_id: string;
  source_type: SourceKind;
  ticker: string;
  title: string;
  source_url: string;
  source_created_at: string;
  source_first_seen_at: string;
  ingested_at: string;
  ticker_confidence: number;
  raw_content_hash: string;
  metadata: Record<string, unknown>;
};

export type SourceStatus = {
  source: string;
  status: "live" | "degraded" | "unavailable";
  provider: string;
  events: number;
  detail: string;
};

export type SignalFeatures = {
  social_count: number;
  unique_authors: number;
  social_acceleration: number;
  social_z: number;
  dd_density: number;
  bull_ratio: number;
  news_count: number;
  news_z: number;
  catalyst_quality: number;
  novelty: number;
  filing_confirmed: boolean;
  market_z: number;
  relative_volume: number;
  abnormal_return_recent: number;
  price_resolution: string;
  pre_signal_return: number;
  social_news_gap: number;
  social_price_gap: number;
  news_price_gap: number;
  already_pumped_penalty: number;
};

export type Playbook = {
  stance: "PAPER_LONG" | "WATCH" | "STAND_ASIDE";
  rationale: string;
  entry_trigger: string;
  invalidation: string;
  time_stop_hours: number;
  max_nav_pct: number;
  expected_holding_period: string;
  risks: string[];
};

export type SignalSnapshot = {
  snapshot_id: string;
  ticker: string;
  company: string;
  signal_generated_at: string;
  phase: Phase;
  conflict: boolean;
  confidence: number;
  features: SignalFeatures;
  evidence_event_ids: string[];
  classifier_version: string;
  signal_version: string;
  dataset_version: string;
  thesis: string;
  action: "WATCH" | "PAPER_BUY" | "NO_TRADE";
};

export type MarketCode = "US" | "IN";

export type ResearchResult = {
  query: string;
  ticker: string;
  display_symbol: string;
  market: MarketCode;
  market_label: string;
  currency: string;
  company: string;
  cik: number;
  resolution_confidence: number;
  generated_at: string;
  snapshot: SignalSnapshot;
  playbook: Playbook;
  events: SourceEvent[];
  coverage: SourceStatus[];
  narrative: string;
  narrative_source: "rules" | "groq";
  warnings: string[];
};

export type Candidate = {
  ticker: string;
  company: string;
  cik: number;
  confidence: number;
  matchedOn: string;
};

export type StrategyResult = {
  strategy: string;
  signals: number;
  win_rate: number;
  mean_excess_return: number;
  confidence_interval: [number, number];
  total_return: number;
  max_drawdown: number;
  turnover: number;
  false_positive_rate: number;
};

export type BacktestCoverage = {
  source: string;
  mode: "historical" | "forward_only" | "unavailable";
  first_observation: string | null;
  last_observation: string | null;
  observations: number;
  detail: string;
};

export type Backtest = {
  run_id: string;
  dataset_version: string;
  dataset_label: string;
  configuration_hash: string;
  code_version: string;
  locked_holdout: boolean;
  status: string;
  strategies: StrategyResult[];
  coverage: BacktestCoverage[];
  caveats: string[];
};

export type SourceHealth = {
  source: string;
  status: string;
  detail: string;
};
