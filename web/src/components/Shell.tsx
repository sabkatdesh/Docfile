import { ChartColumn, ClipboardCheck, LayoutDashboard, Monitor, Moon, Sun } from "lucide-react";
import { NavLink, Outlet } from "react-router";
import { useHealth, useReview } from "../api/queries";
import { type ThemeChoice, useTheme } from "../lib/theme";

const NAV = [
  { to: "/", label: "Dashboard", Icon: LayoutDashboard, end: true },
  { to: "/review", label: "Review queue", Icon: ClipboardCheck, end: false },
  { to: "/evaluation", label: "Evaluation", Icon: ChartColumn, end: false },
] as const;

const THEMES: { value: ThemeChoice; label: string; Icon: typeof Sun }[] = [
  { value: "system", label: "Match system", Icon: Monitor },
  { value: "light", label: "Light", Icon: Sun },
  { value: "dark", label: "Dark", Icon: Moon },
];

function ThemeSwitch() {
  const { choice, setChoice } = useTheme();
  return (
    <fieldset className="m-0 flex rounded-lg border border-line bg-surface p-0.5">
      <legend className="sr-only">Colour theme</legend>
      {THEMES.map(({ value, label, Icon }) => (
        <label key={value} className="relative cursor-pointer">
          <input
            type="radio"
            name="theme"
            value={value}
            checked={choice === value}
            onChange={() => setChoice(value)}
            className="peer sr-only"
          />
          <span
            title={label}
            className="flex h-8 w-8 items-center justify-center rounded-md text-muted peer-checked:bg-accent-bg peer-checked:text-accent-fg peer-focus-visible:outline peer-focus-visible:outline-2 peer-focus-visible:outline-offset-2 peer-focus-visible:outline-accent"
          >
            <Icon size={16} aria-hidden="true" />
            <span className="sr-only">{label}</span>
          </span>
        </label>
      ))}
    </fieldset>
  );
}

export function Shell() {
  const pending = useReview();
  const health = useHealth();
  const waiting = pending.data?.length ?? 0;
  return (
    <>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:fixed focus:left-4 focus:top-4 focus:z-50 focus:rounded-lg focus:bg-accent-bg focus:px-4 focus:py-2 focus:text-accent-fg"
      >
        Skip to content
      </a>
      <header className="border-b border-line bg-surface">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-3 px-4 py-3 sm:px-6">
          <div className="flex items-center gap-2.5">
            <span
              aria-hidden="true"
              className="flex h-8 w-8 items-center justify-center rounded-lg bg-accent-bg text-accent-fg"
            >
              <ClipboardCheck size={18} />
            </span>
            <span className="text-base font-semibold leading-tight">Supplier Document Checker</span>
          </div>
          <nav aria-label="Main" className="flex min-w-[21rem] flex-1 flex-wrap items-center gap-1">
            {NAV.map(({ to, label, Icon, end }) => (
              <NavLink
                key={to}
                to={to}
                end={end}
                className={({ isActive }) =>
                  `inline-flex items-center gap-2 whitespace-nowrap rounded-lg px-3 py-2 text-sm font-medium ${
                    isActive
                      ? "bg-surface-2 text-fg"
                      : "text-muted hover:bg-surface-2 hover:text-fg"
                  }`
                }
              >
                <Icon size={16} aria-hidden="true" />
                {label}
                {to === "/review" && waiting > 0 ? (
                  <span className="rounded-full bg-review-bg px-2 text-xs font-bold text-review-fg ring-1 ring-review-line">
                    {waiting}
                    <span className="sr-only"> waiting</span>
                  </span>
                ) : null}
              </NavLink>
            ))}
          </nav>
          {health.data ? (
            <span className="rounded-md bg-surface-2 px-2.5 py-1 text-xs text-muted">
              {health.data.provider === "replay"
                ? "Demo mode: recorded readings"
                : `Live: ${health.data.model ?? health.data.provider}`}
            </span>
          ) : null}
          <ThemeSwitch />
        </div>
      </header>
      <main id="main" tabIndex={-1} className="mx-auto max-w-7xl px-4 py-8 sm:px-6">
        <Outlet />
      </main>
    </>
  );
}
