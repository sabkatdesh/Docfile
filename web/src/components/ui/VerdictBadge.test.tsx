import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Decision } from "../../api/types";
import { VerdictBadge } from "./VerdictBadge";

const CASES: [Decision, string][] = [
  ["Approve", "approve"],
  ["Reject", "reject"],
  ["Needs a person to check", "review"],
];

describe("VerdictBadge", () => {
  it.each(CASES)("shows the exact wording and its own icon for %s", (decision, icon) => {
    const { container } = render(<VerdictBadge decision={decision} />);
    expect(screen.getByText(decision)).toBeInTheDocument();
    const svg = container.querySelector("svg");
    expect(svg).not.toBeNull();
    expect(svg?.getAttribute("data-icon")).toBe(icon);
    expect(svg?.getAttribute("aria-hidden")).toBe("true"); // the label is the accessible name
  });

  it("uses a different icon for each verdict, so colour is never the only signal", () => {
    const icons = CASES.map(([d]) => {
      const { container, unmount } = render(<VerdictBadge decision={d} />);
      const html = container.querySelector("svg")?.innerHTML;
      unmount();
      return html;
    });
    expect(new Set(icons).size).toBe(3);
  });

  it("carries the label as text, not as something only a stylesheet shows", () => {
    const { container } = render(<VerdictBadge decision="Reject" />);
    expect(container.textContent).toBe("Reject");
  });

  it("says Not run, with an icon, when there is no decision", () => {
    const { container } = render(<VerdictBadge decision={null} />);
    expect(screen.getByText("Not run")).toBeInTheDocument();
    expect(container.querySelector("svg")).not.toBeNull();
  });
});
