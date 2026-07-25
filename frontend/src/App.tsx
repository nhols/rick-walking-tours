import { useEffect, useState } from "react";
import type { Session } from "@supabase/supabase-js";
import { LoaderCircle } from "lucide-react";
import { AuthScreen } from "./components/AuthScreen";
import { TourLibrary } from "./components/TourLibrary";
import { supabase } from "./lib/supabase";


export default function App() {
  const [session, setSession] = useState<Session | null | undefined>(undefined);

  useEffect(() => {
    let active = true;
    void (async () => {
      const { data } = await supabase.auth.getSession();
      const sessionIsValid =
        !data.session || !(await supabase.auth.getUser()).error;
      if (!sessionIsValid) {
        await supabase.auth.signOut({ scope: "local" });
      }
      if (active) setSession(sessionIsValid ? data.session : null);
    })();
    const { data } = supabase.auth.onAuthStateChange((event, nextSession) => {
      if (event !== "INITIAL_SESSION") setSession(nextSession);
    });
    return () => {
      active = false;
      data.subscription.unsubscribe();
    };
  }, []);

  if (session === undefined) {
    return (
      <div className="full-loader">
        <LoaderCircle className="spin" size={26} />Loading Rick…
      </div>
    );
  }
  return session ? <TourLibrary session={session} /> : <AuthScreen />;
}
