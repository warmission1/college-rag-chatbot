import type { Metadata } from 'next';
import { Inter, Outfit } from 'next/font/google';
import './globals.css';

const outfit = Outfit({ subsets: ['latin'], variable: '--font-outfit' });

export const metadata: Metadata = {
  title: 'College RAG Assistant',
  description: 'Official AI-powered college information assistant using Retrieval-Augmented Generation',
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={outfit.variable}>
      <body className="bg-[#0b0f19] text-gray-100 min-h-screen font-sans antialiased">
        {children}
      </body>
    </html>
  );
}
