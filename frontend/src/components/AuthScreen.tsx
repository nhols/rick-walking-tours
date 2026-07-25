import { useState, type FormEvent } from "react";
import { Footprints, LoaderCircle } from "lucide-react";
import { supabase } from "../lib/supabase";


export function AuthScreen() {
  const [email, setEmail] = useState(import.meta.env.DEV ? "demo@rick.local" : "");
  const [password, setPassword] = useState(import.meta.env.DEV ? "password123" : "");
  const [mode, setMode] = useState<"login" | "signup">("login");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const result =
        mode === "login"
          ? await supabase.auth.signInWithPassword({ email, password })
          : await supabase.auth.signUp({ email, password });
      if (result.error) {
        setMessage(result.error.message);
      } else if (mode === "signup" && !result.data.session) {
        setMessage("Check your email to confirm your account, then sign in.");
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Authentication failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="auth-page">
      <form className="auth-card" onSubmit={submit}>
        <div className="brand-lockup">
          <span className="brand-mark"><Footprints size={24} /></span>
          <span>Rick</span>
        </div>
        <header>
          <h1>{mode === "login" ? "Sign in" : "Create an account"}</h1>
          <p>{mode === "login" ? "Manage your walking tours." : "Create and save walking tours."}</p>
        </header>
          <label>
            Email
            <input
              type="email"
              value={email}
              onChange={(event) => setEmail(event.target.value)}
              autoComplete="email"
              required
            />
          </label>
          <label>
            Password
            <input
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              minLength={6}
              required
            />
          </label>
          {message && <p className="form-message">{message}</p>}
          <button className="primary-button wide" disabled={busy}>
            {busy && <LoaderCircle className="spin" size={18} />}
            {mode === "login" ? "Sign in" : "Create account"}
          </button>
          <button
            className="text-button"
            type="button"
            onClick={() => {
              setMode(mode === "login" ? "signup" : "login");
              setMessage(null);
            }}
          >
            {mode === "login"
              ? "New here? Create an account"
              : "Already have an account? Sign in"}
          </button>
      </form>
    </main>
  );
}
