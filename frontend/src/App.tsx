import { useState, useEffect } from 'react';
import type { Session } from '@supabase/supabase-js';
import { supabase } from './lib/supabase';
import Auth from './pages/Auth';
import Dashboard from './pages/Dashboard';
import AuraBackground from './components/visuals/AuraBackground';

// DEV MODE FLAG - set to false for production
const DEV_MODE = false;

function App() {
  const [session, setSession] = useState<Session | null>(null);

  useEffect(() => {
    if (DEV_MODE) {
      // Mock session for development testing
      setSession({
        access_token: "mock-token",
        token_type: "bearer",
        expires_in: 3600,
        refresh_token: "mock-refresh",
        user: {
          id: "dev-user-id",
          aud: "authenticated",
          email: "dev@example.com",
          app_metadata: {},
          user_metadata: {},
          created_at: "",
          role: "",
        }
      } as Session);
      return;
    }

    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
    });

    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
    });

    return () => subscription.unsubscribe();
  }, []);

  return (
    <div className="antialiased text-text-primary selection:bg-primary/30 relative">
      <AuraBackground />
      {session ? (
        <Dashboard key={session.user.id} session={session} />
      ) : (
        <Auth />
      )}
    </div>
  );
}

export default App;
