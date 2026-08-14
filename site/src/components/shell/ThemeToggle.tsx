import { useEffect, useState } from "react";

/**
 * Light or dark, defaulting to what the visitor's system already says.
 *
 * The choice persists. Switching costs one attribute on the root element,
 * because every colour in the system is a custom property rather than a class
 * — no re-render, and no component that knows which mode it is in.
 */

type Theme = "light" | "dark";

const KEY = "beacon-theme";

function stored(): Theme | null {
  const value = localStorage.getItem(KEY);
  return value === "light" || value === "dark" ? value : null;
}

function systemTheme(): Theme {
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

/**
 * Light or dark, defaulting to what the visitor's system already says.
 *
 * Nothing is written to storage until the visitor actually toggles. Persisting
 * the system value on first load looks harmless and silently opts them out:
 * the preference is now pinned, and changing the OS setting later has no
 * effect because a stored value always wins.
 *
 * While no choice has been made, the OS is followed live — a visitor whose
 * machine switches at sunset sees the page switch with it.
 */
export function useTheme(): [Theme | null, () => void] {
  /*
   * `null` until the browser has been asked, on the server *and* on the first
   * client render.
   *
   * This used to resolve during render — `stored() ?? systemTheme()` — which
   * was correct for exactly as long as nothing was prerendered. Once every
   * page ships with its markup already in it, the server has to guess, guesses
   * dark, and a light visitor's first client render disagrees: React reports
   * a hydration mismatch and throws the whole prerendered tree away, which is
   * the one outcome prerendering exists to avoid.
   *
   * So nobody decides during render. `data-theme` is not stamped until the
   * answer is known, and until then the stylesheet's `prefers-color-scheme`
   * block is what paints — which it does before first paint rather than after,
   * so the page arrives in the right theme instead of correcting into it.
   */
  const [theme, setTheme] = useState<Theme | null>(null);
  const [chosen, setChosen] = useState(false);

  useEffect(() => {
    const value = stored();
    setTheme(value ?? systemTheme());
    setChosen(value !== null);
  }, []);

  useEffect(() => {
    if (theme === null) return;
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    if (chosen) return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const follow = () => setTheme(systemTheme());
    media.addEventListener("change", follow);
    return () => media.removeEventListener("change", follow);
  }, [chosen]);

  return [
    theme,
    () => {
      setTheme((current) => {
        const next = current === "dark" ? "light" : "dark";
        localStorage.setItem(KEY, next);
        return next;
      });
      setChosen(true);
    },
  ];
}

export function ThemeToggle({
  theme,
  onToggle,
}: {
  theme: Theme | null;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      // Omitted rather than guessed while the answer is unknown: a toggle that
      // reports a state it has not read is worse than one that reports none,
      // and this is the markup hydration compares.
      aria-pressed={theme === null ? undefined : theme === "dark"}
      aria-label="Switch between light and dark"
      title="Switch between light and dark"
      className="hit-target inline-flex w-9 items-center justify-center rounded-row border border-line-strong text-text-muted hover:text-text"
    >
      {/* A circle half filled — the state, without a word that has to be translated. */}
      <svg width="15" height="15" viewBox="0 0 16 16" aria-hidden="true">
        <circle cx="8" cy="8" r="6.2" fill="none" stroke="currentColor" strokeWidth="1.6" />
        <path d="M8 1.8 A6.2 6.2 0 0 1 8 14.2 Z" fill="currentColor" />
      </svg>
    </button>
  );
}
