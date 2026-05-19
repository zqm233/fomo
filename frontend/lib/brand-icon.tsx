/** FOMO 字母标 — favicon / Sidebar 共用 */

export const BRAND = {
  bg: "#121218",
  bgHi: "#1a1a22",
  purple: "#8b6cf8",
  purpleLight: "#c4b5fd",
} as const;

type BrandIconProps = {
  size?: number;
  className?: string;
  idPrefix?: string;
};

function BrandMark({ idPrefix }: { idPrefix: string }) {
  const g = `${idPrefix}-fg`;
  const bg = `${idPrefix}-bg`;
  return (
    <>
      <defs>
        <linearGradient id={g} x1="4" y1="28" x2="28" y2="4" gradientUnits="userSpaceOnUse">
          <stop stopColor={BRAND.purple} />
          <stop offset="1" stopColor={BRAND.purpleLight} />
        </linearGradient>
        <linearGradient id={bg} x1="0" y1="0" x2="32" y2="32" gradientUnits="userSpaceOnUse">
          <stop stopColor={BRAND.bgHi} />
          <stop offset="1" stopColor={BRAND.bg} />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill={`url(#${bg})`} />
      <text
        x="16"
        y="21"
        textAnchor="middle"
        fill={`url(#${g})`}
        fontFamily="ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif"
        fontSize="8.2"
        fontWeight="800"
        letterSpacing="-0.55"
      >
        FOMO
      </text>
    </>
  );
}

export function BrandIcon({ size = 28, className, idPrefix = "brand" }: BrandIconProps) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 32 32"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      role="img"
      aria-label="FOMO"
    >
      <BrandMark idPrefix={idPrefix} />
    </svg>
  );
}

/** `next/og` ImageResponse — 浏览器标签 / Apple 触控图标 */
export function BrandIconImage({ size }: { size: number }) {
  const radius = Math.round(size * 0.25);
  const fontSize = Math.max(7, Math.round(size * 0.28));

  return (
    <div
      style={{
        width: size,
        height: size,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: `linear-gradient(145deg, ${BRAND.bgHi} 0%, ${BRAND.bg} 100%)`,
        borderRadius: radius,
      }}
    >
      <div
        style={{
          fontSize,
          fontWeight: 800,
          letterSpacing: -fontSize * 0.07,
          color: BRAND.purpleLight,
          fontFamily: "system-ui, -apple-system, sans-serif",
          lineHeight: 1,
        }}
      >
        FOMO
      </div>
    </div>
  );
}
