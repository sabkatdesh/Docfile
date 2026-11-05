import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EventSource as NodeEventSource } from "eventsource";
import { beforeAll, describe, expect, it } from "vitest";
import { setApiBase } from "../src/api/client";
import { renderRealApp } from "./render";

// One walk through the real thing: real API process, real SSE stream, real replayed readings.
describe("smoke: run all, inspect pack 09, resolve it, see it in Evaluation", () => {
  beforeAll(() => {
    const api = process.env.DOCGATE_E2E_API;
    if (!api) throw new Error("globalSetup did not start the API");
    setApiBase(api);
    // jsdom has no EventSource; the polyfill speaks the same protocol to the same server.
    (globalThis as { EventSource?: unknown }).EventSource = NodeEventSource;
  });

  it("works end to end", async () => {
    const user = userEvent.setup();
    renderRealApp("/");

    // 1. Run all. The first run has nothing pending, so no confirmation is expected.
    await user.click(await screen.findByRole("button", { name: "Run all checks" }));
    await waitFor(() => expect(screen.getAllByText("10 of 10")).toHaveLength(2), {
      timeout: 40_000,
    });
    const row = (await screen.findByText("Pack 09")).closest("tr") as HTMLElement;
    expect(within(row).getByText("Needs a person to check")).toBeInTheDocument();

    // 2. Open pack 09: its evidence is highlighted, and selecting a field activates its quote.
    await user.click(within(row).getByRole("link", { name: /^Pack 09/ }));
    const text = await screen.findByTestId("document-text");
    expect(text.querySelectorAll("mark.evidence").length).toBeGreaterThan(0);
    const panel = await screen.findByRole("tabpanel");
    await user.click(within(panel).getByRole("button", { name: /Quantity/ }));
    expect(document.querySelector("mark[data-active='true']")?.textContent).toContain("50,000");

    // 3. Resolve it in the Review queue with a reason.
    const nav = within(screen.getByRole("navigation"));
    await user.click(nav.getByRole("link", { name: /Review queue/ }));
    const cards = await screen.findAllByRole("article");
    const card = cards.find((c) => within(c).queryByText("Pack 09")) as HTMLElement;
    await user.click(within(card).getByRole("radio", { name: "Reject" }));
    await user.type(within(card).getByLabelText("Reason"), "Numbers do not add up.");
    await user.click(within(card).getByRole("button", { name: "Save decision" }));
    await waitFor(() => expect(screen.queryByText("Pack 09")).not.toBeInTheDocument());

    // 4. Evaluation shows the person's decision beside the system's.
    await user.click(nav.getByRole("link", { name: "Evaluation" }));
    const evalRow = (await screen.findByText("Pack 09", { selector: "a" })).closest(
      "tr",
    ) as HTMLElement;
    // expected and system-decided are both "Needs a person"; the person's Reject stands apart
    expect(within(evalRow).getAllByText("Needs a person to check")).toHaveLength(2);
    // the page shows cached data first, then refetches
    await waitFor(() => expect(within(evalRow).getByText("Reject")).toBeInTheDocument());
    expect(await screen.findByText("10 of 10")).toBeInTheDocument();
  });
});
