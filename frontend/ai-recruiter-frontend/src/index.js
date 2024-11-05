import React from 'react';
import ReactDOM from 'react-dom/client';
import { GoogleOAuthProvider } from '@react-oauth/google';
import { AuthProvider } from './contexts/AuthContext';
import ErrorBoundary from './components/ErrorBoundary';
import App from './App';
import './index.css';

const root = ReactDOM.createRoot(document.getElementById('root'));

// Log the client ID for debugging
console.log('Google Client ID:', process.env.REACT_APP_GOOGLE_CLIENT_ID ? 'Present' : 'Missing');

root.render(
  <React.StrictMode>
    <ErrorBoundary>
      <GoogleOAuthProvider 
        clientId={process.env.REACT_APP_GOOGLE_CLIENT_ID}
        onError={(error) => console.error('Google OAuth error:', error)}
      >
        <AuthProvider>  {/* Added AuthProvider */}
          <App />
        </AuthProvider>
      </GoogleOAuthProvider>
    </ErrorBoundary>
  </React.StrictMode>
);