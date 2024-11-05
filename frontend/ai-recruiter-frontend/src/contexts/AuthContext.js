import React, { createContext, useContext, useState, useEffect } from 'react';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    console.log('🔵 Auth Provider Mounted');
    const initAuth = () => {
      const token = localStorage.getItem('token');
      const storedUser = localStorage.getItem('user');
      
      console.log('🟡 Checking stored auth:', {
        hasToken: !!token,
        hasStoredUser: !!storedUser
      });

      if (token && storedUser) {
        try {
          const userData = JSON.parse(storedUser);
          console.log('🟢 Restored auth state for user:', userData.email);
          setUser(userData);
        } catch (error) {
          console.error('🔴 Error restoring auth state:', error);
          localStorage.removeItem('token');
          localStorage.removeItem('user');
        }
      } else {
        console.log('🟡 No stored auth found');
      }
      setLoading(false);
    };

    initAuth();
  }, []);

  const login = async (userData, token) => {
    console.log('🟡 Login called with:', {
      userEmail: userData?.email,
      userRole: userData?.role,
      hasToken: !!token
    });

    setUser(userData);
    localStorage.setItem('token', token);
    localStorage.setItem('user', JSON.stringify(userData));
    console.log('🟢 Auth state updated');
  };

  const logout = () => {
    console.log('🟡 Logout called');
    setUser(null);
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    console.log('🟢 Auth state cleared');
  };

  return (
    <AuthContext.Provider value={{ user, loading, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    console.error('🔴 useAuth must be used within AuthProvider');
    throw new Error('useAuth must be used within AuthProvider');
  }
  return context;
};