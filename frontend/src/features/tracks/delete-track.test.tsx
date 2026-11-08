import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { DeleteTrackControl } from "./DeleteTrackControl";
import { setCsrfToken } from "../../lib/api-client";

afterEach(() => { vi.unstubAllGlobals(); setCsrfToken(null); });

it("requires explicit confirmation and restores focus when cancelled", async () => {
  const user = userEvent.setup(); const fetcher = vi.fn(); vi.stubGlobal("fetch", fetcher);
  render(<DeleteTrackControl crewId="c1" crewTrackId="ct1" title="Fixture" onDeleted={vi.fn()} />);
  await user.click(screen.getByRole("button", { name: "Delete track: Fixture" }));
  expect(screen.getByRole("button", { name: "Cancel deletion" })).toHaveFocus();
  expect(screen.getByText(/does not permanently erase/)).toBeInTheDocument();
  await user.click(screen.getByRole("button", { name: "Cancel deletion" }));
  expect(screen.getByRole("button", { name: "Delete track: Fixture" })).toHaveFocus();
  expect(fetcher).not.toHaveBeenCalled();
});

it("sends CSRF-protected deletion and updates UI only after success", async () => {
  const user = userEvent.setup(); const saved = vi.fn(); setCsrfToken("csrf-fixture");
  const fetcher = vi.fn(async () => new Response(null, { status: 204 })); vi.stubGlobal("fetch", fetcher);
  render(<DeleteTrackControl crewId="c1" crewTrackId="ct1" title="Fixture" onDeleted={saved} />);
  await user.click(screen.getByRole("button", { name: "Delete track: Fixture" }));
  await user.click(screen.getByRole("button", { name: "Delete from crew" }));
  await waitFor(() => expect(saved).toHaveBeenCalledOnce());
  expect(fetcher).toHaveBeenCalledWith("/api/v1/crews/c1/tracks/ct1", expect.objectContaining({ method: "DELETE", headers: { "X-CSRF-Token": "csrf-fixture" } }));
});

it("keeps the track and shows an error after server denial", async () => {
  const user = userEvent.setup(); const saved = vi.fn();
  vi.stubGlobal("fetch", vi.fn(async () => new Response('{"detail":"not allowed"}', { status: 403 })));
  render(<DeleteTrackControl crewId="c1" crewTrackId="ct1" title="Fixture" onDeleted={saved} />);
  await user.click(screen.getByRole("button", { name: "Delete track: Fixture" }));
  await user.click(screen.getByRole("button", { name: "Delete from crew" }));
  expect(await screen.findByRole("alert")).toHaveTextContent("not allowed");
  expect(saved).not.toHaveBeenCalled();
  expect(screen.getByRole("button", { name: "Cancel deletion" })).toBeEnabled();
});
