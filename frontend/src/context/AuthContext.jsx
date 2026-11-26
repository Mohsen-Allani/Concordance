import { createContext, useCallback, useContext, useEffect, useMemo, useState } from 'react';

import * as api from '../api/client.js';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  // loading | authenticated | anonymous
  const [status, setStatus] = useState(api.tokenStore.get() ? 'loading' : 'anonymous');

  useEffect(() => {
    api.setUnauthorizedHandler(() => {
      setUser(null);
      setStatus('anonymous');
    });
    if (!api.tokenStore.get()) return;
    api
      .me()
      .then((u) => {
        setUser(u);
        setStatus('authenticated');
      })
      .catch(() => {
        api.tokenStore.clear();
        setStatus('anonymous');
      });
  }, []);

  const login = useCallback(async (email, password) => {
    const u = await api.login(email, password);
    setUser(u);
    setStatus('authenticated');
    return u;
  }, []);

  const logout = useCallback(() => {
    api.tokenStore.clear();
    setUser(null);
    setStatus('anonymous');
  }, []);

  const value = useMemo(() => ({ user, status, login, logout }), [user, status, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}
