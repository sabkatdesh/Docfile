import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { renderApp, stubApi } from "../../test/harness";

describe("Evaluation", () => {
  it("states the score and the number of unsafe errors", async () => {
    stubApi();
    renderApp("/evaluation");
    expect(await screen.findByText("10 of 10")).toBeInTheDocument();
    expect(screen.getByText(/Nothing was approved that should not have been/)).toBeInTheDocument();
  });

  it("shows the confusion matrix with labelled axes", async () => {
    stubApi();
    renderApp("/evaluation");
    const matrix = await screen.findByRole("table", { name: /expected verdict \(rows\)/i });
    expect(within(matrix).getByText("Expected")).toBeInTheDocument();
    const counts = [...matrix.querySelectorAll("tbody tr")].map((r) =>
      [...r.querySelectorAll("td")].map((td) => td.firstChild?.textContent?.trim()),
    );
    expect(counts).toEqual([
      ["2", "0", "0"],
      ["0", "5", "0"],
      ["0", "0", "3"],
    ]);
  });

  it("lists every stress case under its group", async () => {
    stubApi();
    renderApp("/evaluation");
    await screen.findByText(/39 of 39/);
    expect(document.querySelectorAll("details li")).toHaveLength(39);
  });

  it("explains why the stress tests are unavailable instead of showing zeros", async () => {
    stubApi((c) =>
      c.path === "/api/eval"
        ? {
            body: {
              golden: JSON.parse(JSON.stringify(requireEval().golden)),
              mutation: {
                available: false,
                reason: "No recordings to replay.",
                total: 0,
                passed: 0,
                groups: [],
              },
            },
          }
        : undefined,
    );
    renderApp("/evaluation");
    expect(await screen.findByText("No recordings to replay.")).toBeInTheDocument();
  });

  it("shows the human decision beside the system's, not merged into it", async () => {
    stubApi((c) => {
      if (c.path !== "/api/eval") return undefined;
      const e = requireEval();
      e.golden.rows = e.golden.rows.map((r) =>
        r.pack === 4 ? ({ ...r, human_decision: "Approve" } as unknown as typeof r) : r,
      );
      return { body: e };
    });
    renderApp("/evaluation");
    const row = (await screen.findByText("Pack 04")).closest("tr") as HTMLElement;
    expect(within(row).getAllByText("Needs a person to check").length).toBeGreaterThan(0);
    expect(within(row).getByText("Approve")).toBeInTheDocument();
  });
});

import evalFixture from "../../test/fixtures/eval.json";

function requireEval() {
  return JSON.parse(JSON.stringify(evalFixture)) as typeof evalFixture;
}
