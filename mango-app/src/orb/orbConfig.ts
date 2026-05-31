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

/** Warm amber palette for co-host Amber in duo mode. */
export const AMBER_ORB_TARGETS: typeof ORB_TARGETS = {
  idle: { rgb: [255, 176, 72], rotSpeed: 0.16, breath: 0.007, dotBoost: 1.12 },
  listening: { rgb: [255, 190, 90], rotSpeed: 0.22, breath: 0.011, dotBoost: 1.18 },
  thinking: { rgb: [255, 140, 210], rotSpeed: 0.36, breath: 0.017, dotBoost: 1.32 },
  speaking: { rgb: [255, 120, 40], rotSpeed: 0.58, breath: 0.032, dotBoost: 1.5 },
  awaiting: { rgb: [255, 210, 100], rotSpeed: 0.13, breath: 0.008, dotBoost: 1.15 },
  stopped: { rgb: [160, 140, 120], rotSpeed: 0.08, breath: 0.004, dotBoost: 1.0 },
  error: { rgb: [255, 80, 60], rotSpeed: 0.2, breath: 0.014, dotBoost: 1.25 },
}
