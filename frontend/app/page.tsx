'use client';
import { useEffect } from 'react';

export default function Home() {
  useEffect(() => {
    window.location.replace('/static/index.html');
  }, []);

  return (
    <div style={{
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      minHeight: '100vh',
      background: '#090d16',
      color: '#ffffff',
      fontFamily: 'Outfit, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ fontSize: '3.5rem', marginBottom: '16px', animation: 'pulse 1.5s infinite ease-in-out' }}>🏛️</div>
        <h1 style={{ fontSize: '1.8rem', fontWeight: 700, marginBottom: '8px', letterSpacing: '-0.02em' }}>College RAG Assistant</h1>
        <p style={{ color: '#94a3b8', fontSize: '0.95rem' }}>Loading Campus AI Portal & Knowledge Base...</p>
      </div>
    </div>
  );
}
