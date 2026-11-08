import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, expect, it, vi } from "vitest";
import { ImportControl } from "./ImportControl";

afterEach(() => vi.unstubAllGlobals());

it("renders search results on HTTP phones without crypto.randomUUID", () => {
  const getRandomValues = crypto.getRandomValues.bind(crypto);
  vi.stubGlobal("crypto", { getRandomValues });
  expect(() => render(<MemoryRouter><ImportControl crewId="c1" hit={{ provider: "fake", external_id: "1", title: "Fixture", artist: null, artifact_types: ["lyrics"], source_url: null, attribution: null }} /></MemoryRouter>)).not.toThrow();
  expect(screen.getByRole("button", { name: /Import/ })).toBeEnabled();
});
