import React from 'react';
import { GoogleOAuthProvider } from '@react-oauth/google';

const GoogleAuthWrapper = ({ children }) => {
  const clientId = process.env.REACT_APP_GOOGLE_CLIENT_ID;

  if (!clientId) {
    return (
      <div className="error-message">
        <h1>Configuration Error</h1>
        <p>Google OAuth Client ID is not configured</p>
      </div>
    );
  }

  return (
    <GoogleOAuthProvider clientId={clientId}>
      {children}
    </GoogleOAuthProvider>
  );
};

export default GoogleAuthWrapper;