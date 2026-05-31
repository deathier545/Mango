import type { OrbState } from '../types/ui'

export const ORB_TARGETS: Record<
  OrbState,
  {
    rgb: [number, number, number]
    rotSpeed: number
    breath: number
    dotBoost: number
  }
> = {
  idle: { rgb: [83, 216, 255], rotSpeed: 0.18, breath: 0.006, dotBoost: 1.15 },
  listening: { rgb: [80, 230, 255], rotSpeed: 0.25, breath: 0.01, dotBoost: 1.2 },
  thinking: { rgb: [190, 130, 255], rotSpeed: 0.38, breath: 0.018, dotBoost: 1.35 },
  speaking: { rgb: [255, 72, 38], rotSpeed: 0.62, breath: 0.035, dotBoost: 1.55 },
  awaiting: { rgb: [255, 200, 87], rotSpeed: 0.14, breath: 0.008, dotBoost: 1.2 },
  stopped: { rgb: [148, 156, 170], rotSpeed: 0.08, breath: 0.004, dotBoost: 1.0 },
  error: { rgb: [255, 55, 55], rotSpeed: 0.2, breath: 0.015, dotBoost: 1.3 },
}
