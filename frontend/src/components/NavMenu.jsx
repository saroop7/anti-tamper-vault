import { useEffect, useRef, useState } from "react";
import { useTheme, THEME_ORDER } from "../lib/useTheme";
import { SunIcon, MoonIcon, DiscoIcon, CheckIcon } from "../icons";

function MenuIcon() {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
      <line x1="4" y1="7" x2="20" y2="7" />
      <line x1="4" y1="12" x2="20" y2="12" />
      <line x1="4" y1="17" x2="20" y2="17" />
    </svg>
  );
}

const THEME_META = {
  light: { Icon: SunIcon, label: "Light" },
  dark: { Icon: MoonIcon, label: "Dark" },
  disco: { Icon: DiscoIcon, label: "Disco" },
};

// Hamburger button, top-left of the header -- opens a dropdown holding the
// theme picker (light/dark/disco) and the link to the other page, so the
// header itself stays uncluttered.
export default function NavMenu({ navLink }) {
  const [open, setOpen] = useState(false);
  const [theme, , setTheme] = useTheme();
  const rootRef = useRef(null);

  useEffect(() => {
    if (!open) return;
    function onDocClick(e) {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false);
    }
    function onKey(e) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className="nav-menu" ref={rootRef}>
      <button
        className="nav-menu-trigger"
        onClick={() => setOpen((o) => !o)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Open menu"
      >
        <MenuIcon />
      </button>
      {open ? (
        <div className="nav-menu-panel" role="menu">
          <div className="nav-menu-label">Appearance</div>
          {THEME_ORDER.map((t) => {
            const { Icon, label } = THEME_META[t];
            const active = theme === t;
            return (
              <button
                key={t}
                className={"nav-menu-item" + (active ? " active" : "")}
                role="menuitemradio"
                aria-checked={active}
                onClick={() => {
                  setTheme(t);
                  setOpen(false);
                }}
              >
                <Icon />
                <span>{label}</span>
                {active ? <CheckIcon /> : null}
              </button>
            );
          })}
          {navLink ? (
            <>
              <div className="nav-menu-divider" />
              <a className="nav-menu-item" role="menuitem" href={navLink.href} onClick={() => setOpen(false)}>
                <span>{navLink.label}</span>
              </a>
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
