import type { SoundName } from "@/lib/liveCategories";

/** Short notification sounds made in the browser (no audio files to load). `volume` is 0–100. */
const TONES: Record<SoundName, { freqs: number[]; step: number; length: number; type: OscillatorType }> = {
  chime: { freqs: [880, 1320], step: 0.16, length: 0.3, type: "sine" },
  bell: { freqs: [1046, 1568, 2093], step: 0.02, length: 0.9, type: "triangle" },
  pop: { freqs: [660], step: 0, length: 0.12, type: "square" },
};

export const SOUND_LABELS: Record<SoundName, string> = { chime: "Chime", bell: "Bell", pop: "Pop" };

// Browsers only let a page make sound after the person has clicked or typed on it. One shared audio context is
// "unlocked" by the first click or key press on the admin, so a sound for a new order can play later, unprompted.
let shared: AudioContext | null = null;
function audio(): AudioContext | null {
  if (shared) return shared;
  const AC = window.AudioContext || (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
  shared = AC ? new AC() : null;
  return shared;
}
export function unlockSoundOnFirstInteraction() {
  const unlock = () => {
    void audio()?.resume().catch(() => undefined);
    window.removeEventListener("pointerdown", unlock);
    window.removeEventListener("keydown", unlock);
  };
  window.addEventListener("pointerdown", unlock);
  window.addEventListener("keydown", unlock);
  return unlock;
}
/** False until the browser lets this page play sound (see above). */
export const soundAllowed = () => !!shared && shared.state === "running";

export function playSound(name: SoundName, volume: number) {
  if (volume <= 0) return;
  try {
    const ctx = audio();
    if (!ctx) return;
    if (ctx.state === "suspended") void ctx.resume().catch(() => undefined);
    const tone = TONES[name] ?? TONES.chime;
    const peak = 0.3 * (Math.min(volume, 100) / 100) ** 2 + 0.0002;
    tone.freqs.forEach((freq, i) => {
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = tone.type;
      osc.frequency.value = freq;
      osc.connect(gain);
      gain.connect(ctx.destination);
      const t = ctx.currentTime + i * tone.step;
      gain.gain.setValueAtTime(0.0001, t);
      gain.gain.exponentialRampToValueAtTime(peak, t + 0.015);
      gain.gain.exponentialRampToValueAtTime(0.0001, t + tone.length);
      osc.start(t);
      osc.stop(t + tone.length + 0.05);
    });
  } catch {
    /* no sound is fine */
  }
}
