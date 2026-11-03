declare module '*.webp' {
  const asset: string | { src: string; height?: number; width?: number };
  export default asset;
}
