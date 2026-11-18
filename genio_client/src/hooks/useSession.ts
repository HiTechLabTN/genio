import { useCallback, useEffect, useState } from "react";
import {
  fetchSession,
  signOutSession,
  type SessionUser,
} from "../lib/session";

/** Backend-verified login session (HttpOnly cookie, no local token). */
export function useSession() {
  const [user, setUser] = useState<SessionUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    setLoading(true);
    try {
      setUser(await fetchSession());
    } finally {
      setLoading(false);
    }
  }, []);

  const logout = useCallback(async () => {
    await signOutSession();
    setUser(null);
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  return { user, loading, refresh, logout };
}
