import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { renderApp, review, stubApi } from "../../test/harness";

const firstCard = async () => (await screen.findAllByRole("article"))[0] as HTMLElement;

describe("Review queue", () => {
  it("shows each waiting pack with the rule that needs a person and its quote", async () => {
    stubApi();
    renderApp("/review");
    const card = await firstCard();
    expect(within(card).getByText("Pack 04")).toBeInTheDocument();
    expect(within(card).getByText(/Unit price above the PR maximum/)).toBeInTheDocument();
    expect(within(card).getByText(/6\.65/)).toBeInTheDocument();
  });

  it("blocks a blank reason and sends nothing", async () => {
    const { calls } = stubApi();
    renderApp("/review");
    const card = await firstCard();
    await userEvent.click(within(card).getByRole("radio", { name: "Approve" }));
    await userEvent.type(within(card).getByLabelText("Reason"), "   ");
    await userEvent.click(within(card).getByRole("button", { name: "Save decision" }));
    expect(within(card).getByText(/Write a reason/)).toBeInTheDocument();
    expect(within(card).getByLabelText("Reason")).toHaveFocus();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
  });

  it("requires a decision as well as a reason", async () => {
    const { calls } = stubApi();
    renderApp("/review");
    const card = await firstCard();
    await userEvent.type(within(card).getByLabelText("Reason"), "Looks fine");
    await userEvent.click(within(card).getByRole("button", { name: "Save decision" }));
    expect(within(card).getByText("Choose Approve or Reject.")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(0);
  });

  it("saves a trimmed reason, then the pack leaves the queue", async () => {
    let resolved = false;
    const { calls } = stubApi((c) => {
      if (c.method === "POST" && c.path === "/api/review/supplier-pack-04") {
        resolved = true;
        return { body: { pack_id: "supplier-pack-04", status: "resolved" } };
      }
      if (c.method === "GET" && c.path === "/api/review") {
        return { body: resolved ? review.slice(1) : review };
      }
      return undefined;
    });
    renderApp("/review");
    const card = await firstCard();
    await userEvent.click(within(card).getByRole("radio", { name: "Approve" }));
    await userEvent.type(within(card).getByLabelText("Reason"), "  Within tolerance.  ");
    await userEvent.click(within(card).getByRole("button", { name: "Save decision" }));

    await waitFor(() => expect(screen.queryByText("Pack 04")).not.toBeInTheDocument());
    const post = calls.find((c) => c.method === "POST");
    expect(post?.body).toEqual({ decision: "Approve", reason: "Within tolerance." });
    expect(await screen.findByText(/Pack 04 approved by a person/)).toBeInTheDocument();
  });

  it("shows the server's problem in plain words, such as someone else deciding first", async () => {
    stubApi((c) =>
      c.method === "POST"
        ? {
            status: 409,
            body: {
              error: { code: "already_resolved", message: "already resolved", details: null },
            },
          }
        : undefined,
    );
    renderApp("/review");
    const card = await firstCard();
    await userEvent.click(within(card).getByRole("radio", { name: "Reject" }));
    await userEvent.type(within(card).getByLabelText("Reason"), "Not acceptable");
    await userEvent.click(within(card).getByRole("button", { name: "Save decision" }));
    expect(await within(card).findByRole("alert")).toBeInTheDocument();
  });

  it("says when nothing is waiting", async () => {
    stubApi((c) => (c.path === "/api/review" ? { body: [] } : undefined));
    renderApp("/review");
    expect(await screen.findByText("Nothing is waiting for a person")).toBeInTheDocument();
  });
});
