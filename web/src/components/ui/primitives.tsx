import { Inbox, TriangleAlert } from "lucide-react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type Variant = "primary" | "secondary" | "danger" | "ghost";

const VARIANT: Record<Variant, string> = {
  primary: "bg-accent-bg text-accent-fg hover:brightness-110 border-transparent",
  secondary: "bg-surface text-fg border-control hover:bg-surface-2",
  danger: "bg-reject-fg text-reject-bg border-transparent hover:brightness-110",
  ghost: "bg-transparent text-fg border-transparent hover:bg-surface-2",
};

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  icon?: ReactNode;
}

export function Button({
  variant = "secondary",
  icon,
  children,
  className = "",
  ...rest
}: ButtonProps) {
  return (
    <button
      type="button"
      {...rest}
      className={`inline-flex min-h-10 items-center justify-center gap-2 rounded-lg border px-4 py-2 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-50 ${VARIANT[variant]} ${className}`}
    >
      {icon}
      {children}
    </button>
  );
}

export function Card({
  children,
  className = "",
  as: Tag = "section",
  ...rest
}: {
  children: ReactNode;
  className?: string;
  as?: "section" | "div" | "article";
  "aria-labelledby"?: string;
}) {
  return (
    <Tag
      {...rest}
      className={`rounded-xl border border-line bg-surface p-5 shadow-card ${className}`}
    >
      {children}
    </Tag>
  );
}

export function Skeleton({ className = "" }: { className?: string }) {
  return (
    <div
      aria-hidden="true"
      className={`animate-pulse rounded-md bg-surface-2 ${className}`}
      data-skeleton
    />
  );
}

export function EmptyState({
  title,
  children,
  action,
}: {
  title: string;
  children?: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="flex flex-col items-center gap-3 px-6 py-12 text-center">
      <Inbox size={32} className="text-muted" aria-hidden="true" />
      <h2 className="text-lg font-semibold">{title}</h2>
      {children ? <p className="max-w-md text-muted">{children}</p> : null}
      {action}
    </div>
  );
}

export function ErrorState({
  title = "Something went wrong",
  message,
  onRetry,
}: {
  title?: string;
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div role="alert" className="flex flex-col items-center gap-3 px-6 py-10 text-center">
      <TriangleAlert size={32} className="text-reject-fg" aria-hidden="true" />
      <h2 className="text-lg font-semibold">{title}</h2>
      <p className="max-w-md text-muted">{message}</p>
      {onRetry ? <Button onClick={onRetry}>Try again</Button> : null}
    </div>
  );
}

export function Alert({
  tone,
  children,
}: {
  tone: "error" | "warning" | "info";
  children: ReactNode;
}) {
  const cls = {
    error: "border-reject-line bg-reject-bg text-reject-fg",
    warning: "border-review-line bg-review-bg text-review-fg",
    info: "border-line bg-surface-2 text-fg",
  }[tone];
  return (
    <div
      role={tone === "info" ? "status" : "alert"}
      className={`rounded-lg border px-4 py-3 text-sm ${cls}`}
    >
      {children}
    </div>
  );
}

export function PageTitle({ title, children }: { title: string; children?: ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">{title}</h1>
      {children}
    </div>
  );
}
