import { useCallback, useEffect, useState } from "react";

// Cycles light -> dark -> disco -> light.
export const THEME_ORDER = ["light", "dark", "disco"];

export function getInitialTheme() {
  const saved = localStorage.getItem("theme");
  if (saved) return saved;
  return matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function useTheme() {
  // the pre-paint inline script in index.html/register.html already set
  // data-theme before React mounts, so read it back instead of guessing again
  const [theme, setTheme] = useState(
    () => document.documentElement.getAttribute("data-theme") || getInitialTheme()
  );

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", theme);
    try {
      localStorage.setItem("theme", theme);
    } catch (e) {}
  }, [theme]);

  const cycle = useCallback(() => {
    setTheme((t) => THEME_ORDER[(THEME_ORDER.indexOf(t) + 1) % THEME_ORDER.length]);
  }, []);

  // jump straight to a specific theme (e.g. picked from a menu), instead of
  // stepping through the cycle
  const set = useCallback((next) => {
    if (THEME_ORDER.includes(next)) setTheme(next);
  }, []);

  return [theme, cycle, set];
}
