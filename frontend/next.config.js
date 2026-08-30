/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://college-rag-chatbot-pyly.onrender.com';
    return [
      {
        source: '/api/:path*',
        destination: `${backendUrl}/api/:path*`,
      },
      {
        source: '/',
        destination: '/index.html',
      },
      {
        source: '/chat',
        destination: '/index.html',
      },
      {
        source: '/admin',
        destination: '/index.html',
      },
    ];
  },
};

module.exports = nextConfig;
