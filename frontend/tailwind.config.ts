import type { Config } from "tailwindcss";

const config: Config = {
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        background: "#0d1117",
        card: "#161b22",
        card2: "#21262d",
        accent: "#ecad0a",
        primary: "#209dd7",
        submit: "#753991",
        uptick: "#238636",
        downtick: "#da3633",
      },
      keyframes: {
        flashGreen: {
          '0%': { backgroundColor: 'rgba(35, 134, 54, 0.8)' },
          '100%': { backgroundColor: 'transparent' },
        },
        flashRed: {
          '0%': { backgroundColor: 'rgba(218, 54, 51, 0.8)' },
          '100%': { backgroundColor: 'transparent' },
        }
      },
      animation: {
        'flash-green': 'flashGreen 500ms ease-out',
        'flash-red': 'flashRed 500ms ease-out',
      }
    },
  },
  plugins: [],
};
export default config;
