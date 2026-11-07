import { useState } from "react";
import type { FormEvent } from "react";
import { ApiError, post } from "../../lib/api-client";
import { useGet } from "../../lib/use-api";
import { ErrorNotice, Field, Loading } from "../../components/ui";

interface ProviderStatus {
  provider: string;
  reachable: boolean;
  configured: boolean | null;
  supports_search: boolean;
  supports_fetch: boolean;
  allows_storage: boolean;
  limiter: Record<string, unknown>;
  upstream_requests: number | null;
  error: string | null;
}

export function ProvidersPanel() {
  const { data, error, loading, reload } = useGet<ProviderStatus[]>("/api/v1/admin/providers");
  const [query, setQuery] = useState("");
  const [result, setResult] = useState<unknown>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);

  async function testSearch(event: FormEvent, provider: string) {
    event.preventDefault();
    if (!query.trim()) return;
    setTesting(true);
    setTestError(null);
    setResult(null);
    try {
      const response = await post(`/api/v1/admin/tests/provider-search`, {
        provider,
        query: query.trim(),
      });
      setResult(response);
    } catch (err: unknown) {
      setTestError(err instanceof ApiError ? err.message : "Provider test failed.");
    } finally {
      setTesting(false);
    }
  }

  if (loading) return <Loading label="Loading provider status…" />;
  if (error) return <ErrorNotice message={error} onRetry={reload} />;

  return (
    <section aria-label="Providers">
      <h3>Provider status</h3>
      <p>
        Tests below are isolated: they query providers without touching the library.
        All traffic honors the same rate limits as production.
      </p>
      {(data ?? []).map((provider) => (
        <article key={provider.provider} className="track-card">
          <h4>{provider.provider}</h4>
          {!provider.reachable && (
            <p role="alert">Unreachable: {provider.error ?? "unknown error"}</p>
          )}
          {provider.reachable && (
            <dl>
              <dt>Search</dt>
              <dd>{provider.supports_search ? "yes" : "no"}</dd>
              <dt>Fetch</dt>
              <dd>{provider.supports_fetch ? "yes" : "no"}</dd>
              <dt>Storage allowed</dt>
              <dd>{provider.allows_storage ? "yes" : "no (reference-only)"}</dd>
              <dt>Upstream requests</dt>
              <dd>{provider.upstream_requests ?? "n/a"}</dd>
            </dl>
          )}
          {provider.reachable && provider.supports_search && (
            <form onSubmit={(e) => void testSearch(e, provider.provider)} aria-label={`Test ${provider.provider}`}>
              <Field id={`test-query-${provider.provider}`} label="Test query">
                <input
                  id={`test-query-${provider.provider}`}
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Blue Test Train"
                />
              </Field>
              <button type="submit" disabled={testing}>
                {testing ? "Testing…" : `Search ${provider.provider}`}
              </button>
            </form>
          )}
        </article>
      ))}
      {testError && <ErrorNotice message={testError} />}
      {result !== null && (
        <section aria-label="Provider test result">
          <h4>Result (not stored anywhere)</h4>
          <pre className="doc-panel" tabIndex={0}>
            {JSON.stringify(result, null, 2)}
          </pre>
        </section>
      )}
    </section>
  );
}
