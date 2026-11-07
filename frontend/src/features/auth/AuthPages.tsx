import { useState } from "react";
import type { FormEvent } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";
import { ApiError } from "../../lib/api-client";
import { ErrorNotice, Field, Loading, Page } from "../../components/ui";
import { useAuth } from "./AuthContext";

function redirectTarget(search: string): string {
  const next = new URLSearchParams(search).get("next");
  return next && next.startsWith("/") && !next.startsWith("//") && !next.includes("\\") ? next : "/";
}

export function LoginPage() {
  const { user, loading, login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  if (loading) return <Loading />;
  if (user) {
    return <Navigate to={redirectTarget(location.search)} replace />;
  }

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    if (!username.trim() || !password) {
      setFormError("Enter your username and password.");
      return;
    }
    setSubmitting(true);
    try {
      await login(username.trim(), password);
      navigate(redirectTarget(location.search), { replace: true });
    } catch (err: unknown) {
      setFormError(err instanceof ApiError ? err.message : "Sign in failed.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Page title="Sign in">
      <form onSubmit={onSubmit} noValidate>
        {formError && <ErrorNotice message={formError} />}
        <Field id="username" label="Username" error={undefined}>
          <input
            id="username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
          />
        </Field>
        <Field id="password" label="Password">
          <input
            id="password"
            name="password"
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
          />
        </Field>
        <button type="submit" disabled={submitting}>
          {submitting ? "Signing in…" : "Sign in"}
        </button>
      </form>
      <p>
        New here? <Link to="/request-access">Request access to the jam crew</Link>.
      </p>
    </Page>
  );
}

export function RequestAccessPage() {
  const { requestAccess } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [done, setDone] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setFormError(null);
    if (username.trim().length < 1 || password.length < 8) {
      setFormError("Pick a username and a password of at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      await requestAccess(username.trim(), password);
      setDone(true);
    } catch (err: unknown) {
      setFormError(err instanceof ApiError ? err.message : "Request failed.");
    } finally {
      setSubmitting(false);
    }
  }

  if (done) {
    return (
      <Page title="Request received">
        <p role="status">
          Thanks! An admin will review your request. You can sign in once it is approved.
        </p>
        <p>
          <Link to="/login">Back to sign in</Link>
        </p>
      </Page>
    );
  }

  return (
    <Page title="Request access">
      <form onSubmit={onSubmit} noValidate>
        {formError && <ErrorNotice message={formError} />}
        <Field id="username" label="Username">
          <input
            id="username"
            name="username"
            autoComplete="username"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            required
            minLength={1}
          />
        </Field>
        <Field id="password" label="Password (8+ characters)">
          <input
            id="password"
            name="new-password"
            type="password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={8}
          />
        </Field>
        <button type="submit" disabled={submitting}>
          {submitting ? "Sending…" : "Request access"}
        </button>
      </form>
    </Page>
  );
}
