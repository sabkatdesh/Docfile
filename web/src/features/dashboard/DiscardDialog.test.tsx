import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { DiscardDialog } from "./DiscardDialog";

// jsdom does not implement <dialog> modality; give it the minimum the component relies on.
HTMLDialogElement.prototype.showModal ??= function showModal(this: HTMLDialogElement) {
  this.setAttribute("open", "");
};
HTMLDialogElement.prototype.close ??= function close(this: HTMLDialogElement) {
  this.removeAttribute("open");
  this.dispatchEvent(new Event("close"));
};

describe("DiscardDialog", () => {
  it("names how many reviews would be lost and which packs", () => {
    render(
      <DiscardDialog
        packIds={["supplier-pack-04", "supplier-pack-09"]}
        onCancel={() => {}}
        onConfirm={() => {}}
      />,
    );
    expect(screen.getByText(/discard 2 reviews/i)).toBeInTheDocument();
    expect(screen.getByText("Pack 04")).toBeInTheDocument();
    expect(screen.getByText("Pack 09")).toBeInTheDocument();
  });

  it("uses singular wording for one review", () => {
    render(
      <DiscardDialog packIds={["supplier-pack-07"]} onCancel={() => {}} onConfirm={() => {}} />,
    );
    expect(screen.getByText(/discard 1 review$/i)).toBeInTheDocument();
  });

  it("Cancel only cancels; Discard and run confirms", async () => {
    const onCancel = vi.fn();
    const onConfirm = vi.fn();
    render(
      <DiscardDialog packIds={["supplier-pack-04"]} onCancel={onCancel} onConfirm={onConfirm} />,
    );
    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledOnce();
    expect(onConfirm).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole("button", { name: "Discard and run" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("stays closed when there is nothing to confirm", () => {
    render(<DiscardDialog packIds={null} onCancel={() => {}} onConfirm={() => {}} />);
    expect(document.querySelector("dialog")).not.toHaveAttribute("open");
  });
});
