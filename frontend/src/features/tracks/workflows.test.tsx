import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SuggestTrackForm } from "./SuggestTrackForm";
import { VoteButtons } from "./VoteButtons";
import { clearCsrf } from "../../lib/api-client";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

describe("VoteButtons", () => {
  beforeEach(() => {
    clearCsrf();
    vi.unstubAllGlobals();
  });

  it("casts a vote and reports the new totals", async () => {
    const user = userEvent.setup();
    const seen: { url: string; body: unknown }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (url: string, init?: RequestInit) => {
        seen.push({ url, body: init?.body ? JSON.parse(init.body as string) : null });
        return jsonResponse(200, { vote_score: 4, my_vote: 1 });
      }),
    );
    const onChanged = vi.fn();
    render(
      <VoteButtons crewId="c1" crewTrackId="ct1" score={3} myVote={null} onChanged={onChanged} />,
    );
    await user.click(screen.getByRole("button", { name: "+1" }));
    await waitFor(() => expect(onChanged).toHaveBeenCalledWith(4, 1));
    expect(seen[0].url).toContain("/api/v1/crews/c1/tracks/ct1/vote");
    expect(seen[0].body).toEqual({ value: 1 });
  });

  it("clears an existing vote", async () => {
    const user = userEvent.setup();
    vi.stubGlobal("fetch", vi.fn(async () => new Response(null, { status: 204 })));
    const onChanged = vi.fn();
    render(
      <VoteButtons crewId="c1" crewTrackId="ct1" score={1} myVote={1} onChanged={onChanged} />,
    );
    await user.click(screen.getByRole("button", { name: "Clear" }));
    await waitFor(() => expect(onChanged).toHaveBeenCalledWith(0, null));
  });
});

describe("SuggestTrackForm", () => {
  beforeEach(() => {
    clearCsrf();
    vi.unstubAllGlobals();
  });

  it("submits optional metadata and notifies the parent", async () => {
    const user = userEvent.setup();
    const seen: { body: unknown }[] = [];
    vi.stubGlobal(
      "fetch",
      vi.fn(async (_url: string, init?: RequestInit) => {
        seen.push({ body: init?.body ? JSON.parse(init.body as string) : null });
        return jsonResponse(201, { crew_track_id: "ct9", title: "New Song" });
      }),
    );
    const onCreated = vi.fn();
    render(<SuggestTrackForm crewId="c1" onCreated={onCreated} />);
    await user.click(screen.getByRole("button", { name: "Suggest a track" }));
    await user.type(screen.getByLabelText("Title (optional)"), "New Song");
    await user.type(screen.getByLabelText(/Genres/), "Rock, Folk");
    await user.click(screen.getByRole("button", { name: "Suggest" }));
    await waitFor(() => expect(onCreated).toHaveBeenCalled());
    expect(seen[0].body).toMatchObject({
      title: "New Song",
      artist: null,
      genres: ["Rock", "Folk"],
    });
  });
});
