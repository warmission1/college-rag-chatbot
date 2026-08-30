/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const backendUrl = process.env.NEXT_PUBLIC_BACKEND_URL || 'https://college-rag-chatbot-pyly.onrender.com';
    return {
      beforeFiles: [
        {
          source: '/api/:path*',
          destination: `${backendUrl}/api/:path*`,
        },
        {
          source: '/',
          destination: '/static/index.html',
        },
        {
          source: '/chat',
          destination: '/static/index.html',
        },
        {
          source: '/admin',
          destination: '/static/index.html',
        },
      ],
    };
  },
};

module.exports = nextConfig;
