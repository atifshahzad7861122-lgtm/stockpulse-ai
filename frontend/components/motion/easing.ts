/**
 * The one animation language for UI/chrome motion.
 * Apple-grade: buttery, precise, fast (120–400ms), never bouncy.
 * Leaf module — no imports, safe to pull into any component.
 */

/** The single easing curve — expo-out. */
export const EASE_APPLE: [number, number, number, number] = [0.22, 1, 0.36, 1];

/** Duration scale (seconds). */
export const DUR = { instant: 0.12, fast: 0.18, med: 0.28, slow: 0.4 } as const;

/** Shared transition for overlays: modal / drawer / toast / command bar. */
export const overlayTransition = { duration: DUR.fast, ease: EASE_APPLE } as const;
