import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { MaterialForm } from "./MaterialForm";
import { setCsrfToken } from "../../lib/api-client";

afterEach(() => { vi.unstubAllGlobals(); setCsrfToken(null); });
it("uploads multipart data with CSRF without forcing JSON content type", async () => {
  const fetcher = vi.fn(async () => new Response('{}'));
  vi.stubGlobal("fetch", fetcher); setCsrfToken("test-csrf");
  const saved = vi.fn(); const user = userEvent.setup();
  render(<MaterialForm trackId="t1" versions={[]} onSaved={saved} />);
  await user.click(screen.getByText("Add materials to this track"));
  // A failed save preserves the selected file and any successfully created version.
  fetcher.mockImplementationOnce(async () => new Response('{"id":"v1"}'));
  await user.upload(screen.getByLabelText("File"), new File(["Original fixture"], "lyrics.txt", { type: "text/plain" }));
  await user.click(screen.getByRole("button", { name: "Save material" }));
  await waitFor(() => expect(saved).toHaveBeenCalledOnce());
  const [, options] = (fetcher.mock.calls as unknown as [string, RequestInit][])[1];
  expect(options.body).toBeInstanceOf(FormData);
  expect(options.headers).toEqual({ "X-CSRF-Token": "test-csrf" });
});
it("validates references before sending and retains a draft on server denial", async () => {
  const fetcher = vi.fn(async () => new Response('{"detail":"Denied"}', { status: 403 }));
  vi.stubGlobal("fetch", fetcher);
  const user = userEvent.setup();
  render(<MaterialForm trackId="t1" versions={[]} onSaved={vi.fn()} />);
  await user.click(screen.getByText("Add materials to this track"));
  await user.selectOptions(screen.getByLabelText("Attach by"), "reference");
  await user.click(screen.getByRole("button", { name: "Save material" }));
  expect(fetcher).not.toHaveBeenCalled();
  await user.type(screen.getByLabelText("Source URL"), "https://example.test/music");
  await user.click(screen.getByRole("button", { name: "Save material" }));
  await waitFor(() => expect(screen.getByRole("alert")).toHaveTextContent("Denied"));
  expect(screen.getByLabelText("Source URL")).toHaveValue("https://example.test/music");
});
