import { cn } from '@/lib/utils'

/** [x, amplitude]: where a beat starts along the line, and how tall it is (1 = full, later beats decay like an echo). */
export type Beat = [number, number]

/** A baseline with heartbeat spikes. Same geometry as the Figma "heartbeat" (ECHO — Final). */
function pulsePath(width: number, height: number, beats: Beat[]): string {
  const b = height / 2
  const s = height / 120
  let d = `M0 ${b}`
  for (const [x, a] of beats) {
    d += ` L${x} ${b} L${x + 10 * s} ${b - 18 * a * s} L${x + 22 * s} ${b + 30 * a * s} L${x + 36 * s} ${b - 44 * a * s} L${x + 48 * s} ${b + 14 * a * s} L${x + 56 * s} ${b}`
  }
  return `${d} L${width} ${b}`
}

interface PulseProps {
  width: number
  height: number
  beats: Beat[]
  /** Stroke of the main (mint) line. */
  strokeWidth?: number
  /** Opacity of the main line. */
  opacity?: number
  /** How far below the main line the violet echo sits, in px. 0 hides it. */
  echo?: number
  className?: string
}

/**
 * The heartbeat: a mint line with a violet echo underneath. Decoration only (aria-hidden), never behind text.
 * It scales with its container: give it a width via `className` (`w-full`) and it keeps its aspect ratio.
 */
export function Pulse({ width, height, beats, strokeWidth = 2.5, opacity = 1, echo = 0, className }: PulseProps) {
  const d = pulsePath(width, height, beats)
  return (
    <svg
      aria-hidden
      focusable="false"
      viewBox={`0 0 ${width} ${height + echo}`}
      className={cn('overflow-visible', className)}
      fill="none"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      {echo > 0 && <path d={d} transform={`translate(0 ${echo})`} stroke="#7c69e8" strokeWidth={strokeWidth} opacity={0.55} />}
      <path d={d} stroke="#8ed4ce" strokeWidth={strokeWidth} opacity={opacity} />
    </svg>
  )
}

/** The Echo mark: a violet rounded square holding a single mint heartbeat. */
export function LogoMark({ size = 34, className }: { size?: number; className?: string }) {
  const h = size * 0.7
  return (
    <span
      aria-hidden
      className={cn('grid shrink-0 place-items-center bg-violet-600', className)}
      style={{ width: size, height: size, borderRadius: size * 0.3 }}
    >
      <Pulse width={size * 0.72} height={h} beats={[[size * 0.18, 0.62]]} strokeWidth={2} className="block" />
    </span>
  )
}
