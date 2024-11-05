import React, { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import axios from 'axios';

const AuthCallback = () => {
  const navigate = useNavigate();

  useEffect(() => {
    const handleCallback = async () => {
      const urlParams = new URLSearchParams(window.location.search);
      const code = urlParams.get('code');
      const state = urlParams.get('state');

      try {
        const { data } = await axios.get(
          `http://localhost:8000/auth/google/callback?code=${code}&state=${state}`
        );
        
        localStorage.setItem('token', data.access_token);
        localStorage.setItem('user', JSON.stringify(data.user));
        
        navigate(data.user.role === 'recruiter' ? '/dashboard' : '/interview');
      } catch (error) {
        console.error('Auth callback failed:', error);
        navigate('/login');
      }
    };

    handleCallback();
  }, [navigate]);

  return <div>Processing login...</div>;
};

export default AuthCallback;