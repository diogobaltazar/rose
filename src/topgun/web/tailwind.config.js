/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#f7f7f7",
        panel: "#efefef",
        card: "#ffffff",
        "card-hover": "#f5f5f5",
        amber: {
          tac: "#b87800",
          dim: "#96620a",
          glow: "rgba(184,120,0,0.08)",
        },
        cyan: {
          hud: "#006888",
        },
        red: {
          alert: "#c0200e",
        },
        green: {
          live: "#1a7a3c",
        },
        text: {
          primary: "#111111",
          secondary: "#444444",
          muted: "#777777",
        },
        border: {
          DEFAULT: "rgba(0,0,0,0.10)",
          bright: "rgba(0,0,0,0.22)",
          dim: "rgba(0,0,0,0.05)",
        },
      },
      fontFamily: {
        mono: ['"IBM Plex Mono"', "Menlo", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      keyframes: {
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        pulse_amber: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.3" },
        },
        fadeIn: {
          from: { opacity: "0", transform: "translateY(6px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        flash: {
          "0%":   { color: "#b87800" },
          "40%":  { color: "#b87800" },
          "100%": { color: "currentColor" },
        },
      },
      animation: {
        blink: "blink 1s step-end infinite",
        pulse_amber: "pulse_amber 2s ease-in-out infinite",
        fadeIn: "fadeIn 0.25s ease-out both",
        flash: "flash 0.7s ease-out",
      },
    },
  },
  plugins: [],
};
