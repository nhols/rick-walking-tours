import { useState, type FormEvent } from "react";
import { Footprints, LoaderCircle } from "lucide-react";
import { supabase } from "../lib/supabase";


export function AuthScreen() {
  const [email, setEmail] = useState(import.meta.env.DEV ? "demo@rick.local" : "");
  const [password, setPassword] = useState(import.meta.env.DEV ? "password123" : "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setMessage(null);
    try {
      const result = await supabase.auth.signInWithPassword({ email, password });
      if (result.error) {
        setMessage(result.error.message);
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
          <h1>Sign in</h1>
          <p>Manage your walking tours.</p>
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
              autoComplete="current-password"
              minLength={6}
              required
            />
          </label>
          {message && <p className="form-message">{message}</p>}
          <button className="primary-button wide" disabled={busy}>
            {busy && <LoaderCircle className="spin" size={18} />}
            Sign in
          </button>
          <p className="form-message">Rick is currently invite-only.</p>
      </form>
    </main>
  );
}
