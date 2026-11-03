const isDev = process.env.NODE_ENV === 'development';
const apiPort = process.env.API_PORT ?? '8787';

const nextConfig = {
  ...(!isDev ? { output: 'export' as const } : {}),
  images: {
    unoptimized: true,
  },
  typescript: {
    tsconfigPath: './tsconfig.next.json',
  },
  ...(isDev
    ? {
        async rewrites() {
          return [
            {
              source: '/api/:path*',
              destination: `http://127.0.0.1:${apiPort}/api/:path*`,
            },
          ];
        },
      }
    : {}),
};

export default nextConfig;
