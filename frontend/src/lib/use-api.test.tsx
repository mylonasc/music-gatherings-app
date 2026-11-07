import { act, renderHook, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { useGet, useText } from "./use-api";

afterEach(() => vi.unstubAllGlobals());
it.each(["json", "text"])("clears %s data on key changes, denial, disable, retry and late completion", async (format) => {
  const requests: ((response: Response) => void)[] = [];
  vi.stubGlobal("fetch", vi.fn(() => new Promise<Response>((resolve) => requests.push(resolve))));
  const hook = format === "json" ? useGet : useText;
  const { result, rerender } = renderHook(({ path }) => hook(path), { initialProps: { path: "/a" as string | null } });
  await act(async () => requests[0](new Response(format === "json" ? '{"name":"a"}' : "a")));
  await waitFor(() => expect(result.current.data).not.toBeNull());
  rerender({ path: "/b" });
  expect(result.current.data).toBeNull();
  rerender({ path: "/c" });
  await act(async () => requests[1](new Response(format === "json" ? '{}' : "old")));
  expect(result.current.data).toBeNull();
  await act(async () => requests[2](new Response('{"detail":"Denied"}', { status: 403 })));
  await waitFor(() => expect(result.current.status).toBe(403));
  expect(result.current.data).toBeNull();
  act(() => result.current.reload());
  await act(async () => requests[3](new Response(format === "json" ? '{}' : "new")));
  await waitFor(() => expect(result.current.status).toBe(200));
  rerender({ path: null });
  expect(result.current).toMatchObject({ data: null, error: null, loading: false, status: null });
});
