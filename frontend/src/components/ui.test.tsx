import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { expect, it, vi } from "vitest";
import { Badge, EmptyState, ErrorNotice, Field, Loading, Page } from "./ui";

it("links field errors to the control and preserves hints", () => {
  render(<Field id="title" label="Title" error="Required"><input id="title" aria-describedby="hint" /></Field>);
  expect(screen.getByLabelText("Title")).toHaveAttribute("aria-describedby", "hint title-error");
  expect(screen.getByLabelText("Title")).toHaveAttribute("aria-invalid", "true");
});
it("exposes feedback and an operable retry", async () => {
  const retry = vi.fn();
  render(<Page title="Library"><Loading /><ErrorNotice message="Unavailable" onRetry={retry} /><EmptyState title="No songs">Add one</EmptyState><Badge>Lyrics</Badge></Page>);
  expect(screen.getByRole("heading", { name: "Library" })).toBeInTheDocument();
  expect(screen.getByRole("alert")).toHaveTextContent("Unavailable");
  await userEvent.click(screen.getByRole("button", { name: "Try again" }));
  expect(retry).toHaveBeenCalledOnce();
  expect(screen.getByText("No songs")).toBeInTheDocument();
});
