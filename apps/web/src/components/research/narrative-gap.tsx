import { sigma } from "@/lib/format";
import type { SignalFeatures } from "@/types/research";

const WIDTH = 720;
const HEIGHT = 300;
const PADDING = { top: 34, right: 32, bottom: 52, left: 56 };
const RANGE = 6;

const LAYERS = [
  { key: "social", label: "Reddit", caption: "what the crowd believes", color: "var(--blue)" },
  { key: "news", label: "News", caption: "what the world knows", color: "var(--solar)" },
  { key: "price", label: "Price", caption: "what is already paid for", color: "var(--ink)" },
] as const;

/**
 * The whole thesis in one picture: three standardized layers side by side.
 * The shaded band is the narrative gap — the distance between what is being
 * said and what has been priced.
 */
export function NarrativeGap({
  features,
  socialMeasured = true,
}: {
  features: SignalFeatures;
  socialMeasured?: boolean;
}) {
  const values = [features.social_z, features.news_z, features.market_z];
  const plotWidth = WIDTH - PADDING.left - PADDING.right;
  const plotHeight = HEIGHT - PADDING.top - PADDING.bottom;

  const y = (value: number) =>
    PADDING.top + ((RANGE - Math.max(-2, Math.min(RANGE, value))) / (RANGE + 2)) * plotHeight;
  const x = (index: number) => PADDING.left + (plotWidth / (LAYERS.length - 1)) * index;

  const gridLines = [-2, 0, 2, 4, 6];
  const socialY = y(values[0]);
  const newsY = y(values[1]);

  return (
    <figure className="m-0">
      <figcaption className="flex flex-wrap items-baseline justify-between gap-4">
        <p className="eyebrow text-muted">Narrative gap — social versus news</p>
        {socialMeasured ? (
          <p className={`stat-value ${features.social_news_gap >= 0 ? "text-up" : "text-down"}`}>
            {sigma(features.social_news_gap)}
          </p>
        ) : (
          <p className="stat-value text-muted">—</p>
        )}
      </figcaption>

      {socialMeasured ? null : (
        <p className="mt-4 border-l-2 border-[var(--solar)] bg-[var(--solar-soft)] px-4 py-3 text-sm leading-6 text-ink">
          The social leg did not report. Reddit shows as unmeasured below rather than as zero, and no gap
          is computed — an unmeasured layer is not a quiet one.
        </p>
      )}

      <svg
        viewBox={`0 0 ${WIDTH} ${HEIGHT}`}
        className="mt-5 w-full"
        role="img"
        aria-label={
          socialMeasured
            ? `Social attention ${sigma(values[0])}, news coverage ${sigma(values[1])}, price ${sigma(values[2])}. Narrative gap ${sigma(features.social_news_gap)}.`
            : `Social attention not measured. News coverage ${sigma(values[1])}, price ${sigma(values[2])}. No narrative gap can be computed.`
        }
      >
        {gridLines.map((line) => (
          <g key={line}>
            <line
              x1={PADDING.left - 14}
              x2={WIDTH - PADDING.right}
              y1={y(line)}
              y2={y(line)}
              stroke={line === 0 ? "var(--line-strong)" : "var(--line)"}
              strokeWidth={1}
            />
            <text
              x={PADDING.left - 22}
              y={y(line) + 4}
              textAnchor="end"
              fill="var(--muted)"
              className="tabular"
              fontSize="11"
            >
              {line > 0 ? `+${line}` : line}
            </text>
          </g>
        ))}

        {/* The gap itself, drawn as area rather than left to the reader to infer. */}
        {socialMeasured ? (
          <rect
            x={x(0)}
            y={Math.min(socialY, newsY)}
            width={x(1) - x(0)}
            height={Math.max(2, Math.abs(socialY - newsY))}
            fill={features.social_news_gap >= 0 ? "var(--up-soft)" : "var(--down-soft)"}
          />
        ) : null}

        <polyline
          points={values
            .map((value, index) => (index === 0 && !socialMeasured ? null : `${x(index)},${y(value)}`))
            .filter(Boolean)
            .join(" ")}
          fill="none"
          stroke="var(--ink)"
          strokeWidth={1.5}
          strokeDasharray="4 4"
        />

        {LAYERS.map((layer, index) => {
          const unmeasured = index === 0 && !socialMeasured;
          return (
          <g key={layer.key}>
            <line
              x1={x(index)}
              x2={x(index)}
              y1={unmeasured ? PADDING.top : y(values[index])}
              y2={HEIGHT - PADDING.bottom}
              stroke="var(--line-strong)"
              strokeWidth={1}
              strokeDasharray={unmeasured ? "3 4" : undefined}
            />
            {unmeasured ? null : (
              <circle cx={x(index)} cy={y(values[index])} r={8} fill={layer.color} stroke="var(--paper)" strokeWidth={3} />
            )}
            <text
              x={x(index)}
              y={unmeasured ? PADDING.top + 60 : y(values[index]) - 18}
              textAnchor="middle"
              fill={unmeasured ? "var(--muted)" : "var(--ink)"}
              className="tabular"
              fontSize={unmeasured ? "12" : "15"}
              fontWeight="600"
            >
              {unmeasured ? "not measured" : sigma(values[index])}
            </text>
            <text
              x={x(index)}
              y={HEIGHT - PADDING.bottom + 22}
              textAnchor="middle"
              fill="var(--ink)"
              fontSize="13"
              fontWeight="700"
            >
              {layer.label}
            </text>
            <text
              x={x(index)}
              y={HEIGHT - PADDING.bottom + 40}
              textAnchor="middle"
              fill="var(--muted)"
              fontSize="11"
            >
              {layer.caption}
            </text>
          </g>
          );
        })}
      </svg>
    </figure>
  );
}
