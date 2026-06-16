// A clean, license-free retro/studio microphone drawn as inline SVG.
// `color` drives the stroke so it matches the button state (cyan idle / amber live).
export default function RetroMic({ size = 74, color = 'currentColor' }) {
  return (
    <svg width={size} height={size} viewBox="0 0 64 64" fill="none"
      stroke={color} strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      {/* mic head (rounded capsule) with a subtle grille */}
      <rect x="20" y="6" width="24" height="34" rx="12" fill="rgba(52,225,232,0.08)" />
      <line x1="24" y1="15" x2="40" y2="15" opacity="0.55" />
      <line x1="24" y1="21" x2="40" y2="21" opacity="0.55" />
      <line x1="24" y1="27" x2="40" y2="27" opacity="0.55" />
      <line x1="24" y1="33" x2="40" y2="33" opacity="0.55" />
      {/* yoke / mount arms */}
      <path d="M16 24v6a16 16 0 0 0 32 0v-6" />
      {/* stem */}
      <line x1="32" y1="46" x2="32" y2="54" />
      {/* base */}
      <rect x="22" y="54" width="20" height="5" rx="2.5" fill="rgba(52,225,232,0.12)" />
    </svg>
  )
}
