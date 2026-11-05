import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import errorPending from "../../test/fixtures/error-pending-reviews.json";
import { renderApp, stubApi } from "../../test/harness";

HTMLDialogElement.prototype.showModal ??= function showModal(this: HTMLDialogElement) {
  this.setAttribute("open", "");
};
HTMLDialogElement.prototype.close ??= function close(this: HTMLDialogElement) {
  this.removeAttribute("open");
  this.dispatchEvent(new Event("close"));
};

describe("Dashboard", () => {
  it("shows the verdict for every pack with its label, not only a colour", async () => {
    stubApi();
    renderApp("/");
    await screen.findByText("Pack 01");
    expect(screen.getAllByText("Approve").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Reject").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Needs a person to check").length).toBeGreaterThan(0);
  });

  it("does not show the raw evidence markup in the main reason", async () => {
    stubApi();
    renderApp("/");
    await screen.findByText("Pack 01");
    expect(screen.queryByText(/\[evidence:/)).not.toBeInTheDocument();
  });

  it("shows an empty state before any run", async () => {
    stubApi((c) =>
      c.path === "/api/packs"
        ? {
            body: [
              {
                pack_id: "supplier-pack-01",
                source_file: "supplier-pack-01.pdf",
                supplier: "Padma Textile Mills Ltd",
                item: "A",
                status: "not_run",
                decision: null,
                human_decision: null,
                primary_rule: null,
                headline: null,
              },
            ],
          }
        : undefined,
    );
    renderApp("/");
    expect(await screen.findByText("No packs checked yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Run all checks" })).toBeEnabled();
  });

  it("shows an error with a retry when the packs cannot be loaded", async () => {
    stubApi((c) =>
      c.path === "/api/packs"
        ? { status: 500, body: { error: { code: "internal", message: "boom", details: null } } }
        : undefined,
    );
    renderApp("/");
    expect(await screen.findByRole("button", { name: "Try again" })).toBeInTheDocument();
  });

  it("asks before discarding waiting reviews, and sends discard_pending only on confirm", async () => {
    const { calls } = stubApi((c) => {
      if (c.method !== "POST" || c.path !== "/api/runs") return undefined;
      const body = c.body as { discard_pending: boolean };
      if (!body.discard_pending) return { status: 409, body: errorPending };
      return { status: 202, body: { run_id: "r1", events_url: "/api/runs/r1/events" } };
    });
    renderApp("/");
    const run = await screen.findByRole("button", { name: "Run all again" });
    await userEvent.click(run);

    expect(await screen.findByText(/discard 3 reviews/i)).toBeInTheDocument();
    const posts = () => calls.filter((c) => c.method === "POST");
    expect(posts()).toHaveLength(1);
    expect(posts()[0]?.body).toMatchObject({ discard_pending: false });

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(posts()).toHaveLength(1); // cancelling must not resend anything

    await userEvent.click(await screen.findByRole("button", { name: "Run all again" }));
    await userEvent.click(await screen.findByRole("button", { name: "Discard and run" }));
    await waitFor(() => expect(posts()).toHaveLength(3));
    expect(posts()[2]?.body).toMatchObject({ discard_pending: true });
  });
});
