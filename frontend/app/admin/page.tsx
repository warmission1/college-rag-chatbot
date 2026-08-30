'use client';
import { useEffect } from 'react';

export default function AdminPage() {
  useEffect(() => {
    window.location.replace('/static/index.html');
  }, []);

  return null;
}
