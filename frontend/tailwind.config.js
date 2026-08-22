/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          950: "#0B0D17",
          900: "#0F1220",
          800: "#171B2E",
          700: "#232842",
          600: "#333A5C",
        },
        parchment: {
          100: "#F3EFE4",
          300: "#E7E1D2",
          500: "#B9B3A2",
        },
        gold: {
          400: "#D9B44A",
          500: "#C9A227",
          600: "#A8841C",
        },
        arcane: {
          400: "#8B93FF",
          500: "#6E7BFF",
          600: "#5561D6",
        },
      },
      fontFamily: {
        display: ["'Fraunces'", "serif"],
        mono: ["'IBM Plex Mono'", "monospace"],
      },
      keyframes: {
        pulse_glow: {
          "0%, 100%": { opacity: 0.35, transform: "scale(0.9)" },
          "50%": { opacity: 1, transform: "scale(1.1)" },
        },
      },
      animation: {
        pulse_glow: "pulse_glow 1.4s ease-in-out infinite",
      },
    },
  },
  plugins: [],
};
