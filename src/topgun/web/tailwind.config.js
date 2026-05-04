/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#121212",
        panel: "#1a1a1a",
        card: "#1e1e1e",
        "card-hover": "#242424",
        amber: {
          tac: "#FFB800",
          dim: "#cc9400",
          glow: "rgba(255,184,0,0.15)",
        },
        cyan: {
          hud: "#00d4ff",
        },
        red: {
          alert: "#ff3b30",
        },
        green: {
          live: "#00c853",
        },
        text: {
          primary: "#e8e8e8",
          secondary: "#888888",
          muted: "#555555",
        },
        border: {
          DEFAULT: "rgba(255,184,0,0.18)",
          bright: "rgba(255,184,0,0.45)",
          dim: "rgba(255,255,255,0.06)",
        },
      },
      fontFamily: {
        mono: ['"IBM Plex Mono"', "Menlo", "monospace"],
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      backgroundImage: {
        "dot-grid":
          "radial-gradient(circle, rgba(255,184,0,0.08) 1px, transparent 1px)",
      },
      backgroundSize: {
        "dot-sm": "24px 24px",
        "dot-md": "32px 32px",
      },
      boxShadow: {
        amber: "0 0 20px rgba(255,184,0,0.12)",
        "amber-lg": "0 0 40px rgba(255,184,0,0.18)",
        "amber-inset": "inset 0 0 20px rgba(255,184,0,0.05)",
      },
      keyframes: {
        scanline: {
          "0%": { transform: "translateY(-100%)" },
          "100%": { transform: "translateY(100vh)" },
        },
        blink: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0" },
        },
        pulse_amber: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.4" },
        },
        fadeIn: {
          from: { opacity: "0", transform: "translateY(10px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
      },
      animation: {
        scanline: "scanline 8s linear infinite",
        blink: "blink 1s step-end infinite",
        pulse_amber: "pulse_amber 2s ease-in-out infinite",
        fadeIn: "fadeIn 0.35s ease-out both",
      },
    },
  },
  plugins: [],
};
