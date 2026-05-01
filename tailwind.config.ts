import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#08111f",
        graphite: "#111827",
        signal: "#3dd6c6",
      },
      boxShadow: {
        panel: "0 24px 80px rgba(5, 12, 24, 0.18)",
      },
    },
  },
  plugins: [],
};

export default config;
