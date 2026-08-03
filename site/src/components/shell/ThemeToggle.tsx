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
export function useTheme(): [Theme, () => void] {
  const [theme, setTheme] = useState<Theme>(() =>
    typeof window === "undefined" ? "dark" : (stored() ?? systemTheme()),
  );
  const [chosen, setChosen] = useState<boolean>(() =>
    typeof window === "undefined" ? false : stored() !== null,
  );

  useEffect(() => {
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

export function ThemeToggle({ theme, onToggle }: { theme: Theme; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-pressed={theme === "dark"}
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
