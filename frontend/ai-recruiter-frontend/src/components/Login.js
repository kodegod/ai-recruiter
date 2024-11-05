import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { GoogleLogin } from '@react-oauth/google';
import { useAuth } from '../contexts/AuthContext';

const Login = () => {
  const navigate = useNavigate();
  const { login } = useAuth();

  useEffect(() => {
    console.log('Environment Check:', {
      currentOrigin: window.location.origin,
      clientId: process.env.REACT_APP_GOOGLE_CLIENT_ID
    });
  }, []);

  const handleGoogleSuccess = async (credentialResponse) => {
    try {
      console.log('Google Auth Response:', credentialResponse);
  
      const response = await fetch(`${process.env.REACT_APP_API_URL}/auth/google-login`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          token: credentialResponse.credential
        }),
        credentials: 'include'
      });
  
      if (!response.ok) {
        // Log the error response
        const errorText = await response.text();
        console.error('Server error:', errorText);
        throw new Error(errorText || 'Login failed');
      }
  
      const data = await response.json();
      console.log('Login Success:', data);
  
      await login(data.user, data.access_token);
      navigate(data.user.role === 'recruiter' ? '/dashboard' : '/interview');
      
    } catch (error) {
      console.error('Login error:', error);
      alert('Login failed. Please try again.');
    }
  };

  const handleGoogleError = (error) => {
    console.error('Google Sign In Error:', error);
    alert('Login failed. Please try again.');
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h2 className="mt-6 text-center text-3xl font-extrabold text-gray-900">
            Sign in to AI Recruiter
          </h2>
          <p className="mt-2 text-center text-sm text-gray-600">
            Use your Google account to continue
          </p>
        </div>

        <div className="mt-8 space-y-6">
          <div className="flex justify-center">
            <GoogleLogin
              onSuccess={handleGoogleSuccess}
              onError={handleGoogleError}
              useOneTap={false}
              auto_select={false}
              theme="outline"
              size="large"
              text="signin_with"
              shape="rectangular"
              logo_alignment="left"
              type="standard"
            />
          </div>
        </div>
      </div>
    </div>
  );
};

export default Login;