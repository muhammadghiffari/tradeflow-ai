"use client";

interface CRSGaugeProps {
  score: number; // 0–100
  grade: string; // A, B, C, D, F
  size?: number;
}

const GRADE_COLORS: Record<string, string> = {
  A: "#22c55e",
  B: "#3b82f6",
  C: "#f59e0b",
  D: "#f97316",
  F: "#ef4444",
};

export function CRSGauge({ score, grade, size = 160 }: CRSGaugeProps) {
  const color = GRADE_COLORS[grade] ?? "#3b82f6";
  const cx = size / 2;
  const cy = size / 2;
  const r = (size / 2) * 0.78;
  const strokeWidth = size * 0.075;

  // Arc: 270° sweep (from -135° to 135°)
  const arcStart = 225; // degrees
  const arcSweep = 270;
  const pct = Math.min(Math.max(score, 0), 100) / 100;

  function polarToCartesian(cx: number, cy: number, r: number, angleDeg: number) {
    const rad = ((angleDeg - 90) * Math.PI) / 180;
    return { x: cx + r * Math.cos(rad), y: cy + r * Math.sin(rad) };
  }

  function describeArc(startAngle: number, endAngle: number) {
    const s = polarToCartesian(cx, cy, r, startAngle);
    const e = polarToCartesian(cx, cy, r, endAngle);
    const large = endAngle - startAngle > 180 ? 1 : 0;
    return `M ${s.x} ${s.y} A ${r} ${r} 0 ${large} 1 ${e.x} ${e.y}`;
  }

  const bgEnd = arcStart + arcSweep;
  const fgEnd = arcStart + arcSweep * pct;

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size} className="crs-gauge overflow-visible">
        {/* Background track */}
        <path
          d={describeArc(arcStart, bgEnd)}
          fill="none"
          stroke="rgba(255,255,255,0.08)"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
        />
        {/* Score arc */}
        <path
          d={describeArc(arcStart, fgEnd)}
          fill="none"
          stroke={color}
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          style={{ filter: `drop-shadow(0 0 8px ${color}88)` }}
        />
        {/* Score text */}
        <text
          x={cx}
          y={cy - 4}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="white"
          fontSize={size * 0.22}
          fontWeight="700"
          fontFamily="Inter, sans-serif"
        >
          {Math.round(score)}
        </text>
        <text
          x={cx}
          y={cy + size * 0.14}
          textAnchor="middle"
          fill="rgba(255,255,255,0.45)"
          fontSize={size * 0.09}
          fontFamily="Inter, sans-serif"
        >
          / 100
        </text>
        {/* Grade */}
        <text
          x={cx}
          y={cy + size * 0.28}
          textAnchor="middle"
          fill={color}
          fontSize={size * 0.13}
          fontWeight="700"
          fontFamily="Inter, sans-serif"
        >
          Grade {grade}
        </text>
      </svg>
      <p className="text-xs text-muted-foreground">Customs Readiness Score</p>
    </div>
  );
}
