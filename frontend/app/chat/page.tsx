'use client';
import { useEffect } from 'react';

export default function ChatPage() {
  useEffect(() => {
    window.location.replace('/static/index.html');
  }, []);

  return null;
}
