import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { pack09, renderApp, stubApi } from "../../test/harness";

describe("Pack detail (pack 09)", () => {
  it("highlights the quoted evidence in the document text", async () => {
    stubApi();
    renderApp("/packs/supplier-pack-09");
    const text = await screen.findByTestId("document-text");
    const marks = text.querySelectorAll("mark.evidence");
    expect(marks.length).toBeGreaterThan(0);
    // every highlighted piece is a real substring of the document, nothing invented
    for (const m of marks) expect(pack09.text).toContain(m.textContent ?? "");
  });

  it("shows the verdict with its label and the arithmetic mismatch", async () => {
    stubApi();
    renderApp("/packs/supplier-pack-09");
    expect(await screen.findByText("Needs a person to check")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("tab", { name: /Comparison/ }));
    expect(await screen.findByText("Does not match")).toBeInTheDocument();
    expect(screen.getByText(/Expected 320,000\.00, quote says 322,000\.00/)).toBeInTheDocument();
  });

  it("selecting a field marks its quote active and scrolls to it", async () => {
    stubApi();
    const scroll = vi.fn();
    Element.prototype.scrollIntoView = scroll;
    renderApp("/packs/supplier-pack-09");
    const fields = await screen.findByRole("tabpanel");
    await userEvent.click(within(fields).getByRole("button", { name: /Quantity/ }));
    const active = document.querySelectorAll("mark[data-active='true']");
    expect(active.length).toBeGreaterThan(0);
    expect(active[0]?.textContent).toContain("50,000");
    expect(scroll).toHaveBeenCalled();
  });

  it("lists the failing rules by their plain-English title", async () => {
    stubApi();
    renderApp("/packs/supplier-pack-09");
    await userEvent.click(await screen.findByRole("tab", { name: /Rules/ }));
    const panel = await screen.findByRole("tabpanel");
    expect(within(panel).getAllByText("Fail").length).toBe(2);
  });

  it("moves between tabs with the arrow keys", async () => {
    stubApi();
    renderApp("/packs/supplier-pack-09");
    const fieldsTab = await screen.findByRole("tab", { name: /Fields/ });
    fieldsTab.focus();
    await userEvent.keyboard("{ArrowRight}");
    expect(screen.getByRole("tab", { name: /Comparison/ })).toHaveFocus();
    expect(screen.getByRole("tab", { name: /Comparison/ })).toHaveAttribute(
      "aria-selected",
      "true",
    );
  });

  it("explains a pack that has not been run", async () => {
    stubApi((c) =>
      c.path === "/api/packs/supplier-pack-09"
        ? {
            status: 404,
            body: { error: { code: "no_result", message: "no result", details: null } },
          }
        : undefined,
    );
    renderApp("/packs/supplier-pack-09");
    expect(await screen.findByText(/has not been checked yet/)).toBeInTheDocument();
  });
});
