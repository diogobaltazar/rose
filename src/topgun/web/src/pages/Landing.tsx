import { useEffect } from "react";
import { useAuth0 } from "@auth0/auth0-react";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import HUDGrid from "../components/HUDGrid";
import Terminal from "../components/Terminal";

const INSTALL_LINES = [
  "# alias topgun='docker run ... ghcr.io/diogobaltazar/topgun:latest'",
  "$ topgun install",
  "  Merging settings.json...",
  "  Installing agents...",
  "  ✓ Claude Code armed.",
  "$ topgun upgrade",
  "  Syncing...",
  "  ✓ Configuration up to date.",
  "// Ready to launch missions.",
];

const FEATURES = [
  {
    tag: "01 — MISSIONS",
    title: "GitHub Issues or Obsidian Tasks as Mission Briefs",
    desc: "Label any issue/task topgun-mission and it appears in your dashboard — complete with acceptance criteria, priority, and full briefing.",
  },
  {
    tag: "02 — ENGAGEMENTS",
    title: "Autonomous End-to-End Execution",
    desc: "After mission planning, each engagement runs the full cycle: reconnaissance, implementation, testing, deployment, and merge. Zero human-in-the-loop.",
  },
  {
    tag: "03 — INTELLIGENCE",
    title: "Real-time Mission Logs",
    desc: "Every tool call, every agent spawn, every token spent — streamed live. Full post-mission debrief with cost and performance telemetry.",
  },
];

const PRODUCTS = [
  {
    code: "AMC-01",
    name: "TOPGUN",
    tagline: "Elite Autonomous Development",
    available: true,
    desc: "The weapons school where Claude Code pilots are forged. A team lead agent and a wingman fleet receive their briefing, are dispatched into the codebase, and return with a ready to merge PR. Every engagement sharpens the squadron — a debrief logged, a lesson learned, a sharper pilot on the next sortie.",
    cta: "Launch Mission Control →",
  },
  {
    code: "AMC-02",
    name: "VICTORIA",
    tagline: "Repository Fleet Command",
    available: false,
    desc: "Given a codebase(s), The Alma Victoria fleet reads every open issue, reviews every PR, and meticulously plans the missions campaign with you. Once clarified, it then dispatches the fleet to engage autonomously until all the missions have succeeded, effectively closing all the issues in your project, leaving pending those which require further human input.",
    cta: "Coming Soon",
  },
  {
    code: "AMC-03",
    name: "ALMA VICTORIA ENTERPRISE",
    tagline: "Standing Fleet Protection",
    available: false,
    desc: "A permanent fleet assigned to your production application. Victoria Enterprise monitors health, analyses every code change for downstream impact, and intervenes before there is downtime. You are not paged — the fleet handles it.",
    cta: "Coming Soon",
  },
];

const fade = {
  hidden: { opacity: 0, y: 16 },
  show: (i: number) => ({ opacity: 1, y: 0, transition: { delay: i * 0.12, duration: 0.5 } }),
};

export default function Landing() {
  const { loginWithRedirect, isAuthenticated, isLoading } = useAuth0();
  const navigate = useNavigate();

  useEffect(() => {
    if (!isLoading && isAuthenticated) navigate("/deck/missions");
  }, [isAuthenticated, isLoading, navigate]);

  return (
    <div className="min-h-screen bg-base text-text-primary overflow-x-hidden">
      <HUDGrid />

      {/* Nav */}
      <nav className="relative z-20 flex items-center justify-between px-6 sm:px-12 py-6">
        <span className="font-mono text-sm font-bold tracking-[0.35em] text-white/80">ALMA VICTORIA</span>
        <button
          onClick={() => loginWithRedirect()}
          className="btn-amber text-xs"
        >
          Authorize Access
        </button>
      </nav>

      {/* Hero */}
      <section className="relative z-10 flex flex-col items-center justify-center text-center pt-16 pb-28 px-6">
        <motion.div
          className="mb-6"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 0.8 }}
        >
          <div className="font-mono text-xs text-text-muted tracking-[0.5em] uppercase mb-8">
            AUTONOMOUS MISSION CONTROL
          </div>

          <div className="relative inline-block bracket-corners px-6 py-2">
            <h1 className="font-mono font-bold text-[2.8rem] sm:text-[5rem] tracking-[0.6em] text-white leading-none">
              ALMA <span className="text-amber-tac">VICTORIA</span>
            </h1>
          </div>

          <p className="mt-8 font-mono text-sm text-text-secondary max-w-lg mx-auto leading-relaxed tracking-wide">
            Deploy autonomous development missions with Claude Code.
            <br />
            From GitHub issue to merged PR — zero human-in-the-loop.
          </p>

          <div className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-4">
            <motion.button
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.97 }}
              onClick={() => loginWithRedirect()}
              className="btn-amber-fill"
            >
              Launch TOPGUN Mission Control →
            </motion.button>
            <a
              href="#install"
              className="font-mono text-xs text-text-muted hover:text-amber-tac transition-colors tracking-widest uppercase"
            >
              Installation Guide ↓
            </a>
          </div>
        </motion.div>

        {/* Telemetry strip */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ delay: 0.6, duration: 0.6 }}
          className="mt-16 flex items-center gap-8 sm:gap-16 border-t border-b border-border-dim py-4"
        >
          {[
            { label: "PROTOCOL", value: "ZERO-HUMAN-IN-THE-LOOP" },
            { label: "ENGINE", value: "CLAUDE CODE" },
            { label: "MISSIONS", value: "GITHUB + OBSIDIAN" },
          ].map((t) => (
            <div key={t.label} className="text-center">
              <div className="telemetry-label mb-1">{t.label}</div>
              <div className="font-mono text-xs text-amber-tac tracking-wider">{t.value}</div>
            </div>
          ))}
        </motion.div>
      </section>

      {/* Install */}
      <section id="install" className="relative z-10 py-20 px-6 sm:px-12 max-w-3xl mx-auto">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          variants={fade}
          custom={0}
        >
          <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-2">
            — Installation
          </div>
          <h2 className="font-mono text-xl font-semibold mb-8 text-text-primary">
            Armed in three commands.
          </h2>
          <Terminal lines={INSTALL_LINES} typingSpeed={32} />
          <p className="mt-4 font-mono text-xs text-text-muted">
            Requires Docker and a Claude Code subscription.
          </p>
        </motion.div>
      </section>

      {/* Features */}
      <section className="relative z-10 py-20 px-6 sm:px-12 max-w-5xl mx-auto">
        <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-2">
          — Capabilities
        </div>
        <h2 className="font-mono text-xl font-semibold mb-12 text-text-primary">
          Full-spectrum autonomous execution.
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0 border border-border-dim">
          {FEATURES.map((f, i) => (
            <motion.div
              key={f.tag}
              initial="hidden"
              whileInView="show"
              whileHover={{ scale: 1.03, zIndex: 1 }}
              viewport={{ once: true }}
              variants={fade}
              custom={i}
              className={`p-6 border-border-dim hover:bg-card-hover transition-colors group relative
                ${i < FEATURES.length - 1 ? "border-r" : ""}`}
            >
              <div className="font-mono text-xs text-amber-tac tracking-widest mb-3">{f.tag}</div>
              <h3 className="font-mono text-sm font-semibold text-text-primary mb-2 group-hover:text-amber-tac transition-colors">
                {f.title}
              </h3>
              <p className="text-xs text-text-secondary leading-relaxed">{f.desc}</p>
            </motion.div>
          ))}
        </div>
      </section>

      {/* Products */}
      <section className="relative z-10 py-20 px-6 sm:px-12 max-w-5xl mx-auto">
        <div className="font-mono text-xs text-amber-tac tracking-[0.4em] uppercase mb-2">
          — Fleet
        </div>
        <h2 className="font-mono text-xl font-semibold mb-12 text-text-primary">
          Autonomous mission systems.
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-0 border border-border-dim">
          {PRODUCTS.map((p, i) => (
            <motion.div
              key={p.code}
              initial="hidden"
              whileInView="show"
              whileHover={{ scale: 1.03, zIndex: 1 }}
              viewport={{ once: true }}
              variants={fade}
              custom={i}
              className={`p-6 border-border-dim transition-colors group flex flex-col relative
                ${i < PRODUCTS.length - 1 ? "border-r" : ""}
                ${p.available ? "hover:bg-card-hover" : "opacity-60"}`}
            >
              <div className="flex items-center justify-between mb-3">
                <div className="font-mono text-xs text-amber-tac tracking-widest">{p.code}</div>
                {p.available ? (
                  <span className="font-mono text-[10px] text-green-400 border border-green-400/30 px-2 py-0.5 tracking-widest">ACTIVE</span>
                ) : (
                  <span className="font-mono text-[10px] text-text-muted border border-border-dim px-2 py-0.5 tracking-widest">CLASSIFIED</span>
                )}
              </div>
              <h3 className={`font-mono text-sm font-bold mb-1 tracking-wider transition-colors
                ${p.available ? "text-text-primary group-hover:text-amber-tac" : "text-text-secondary"}`}>
                {p.name}
              </h3>
              <div className="font-mono text-[10px] text-text-muted tracking-widest mb-3 uppercase">{p.tagline}</div>
              <p className="text-xs text-text-secondary leading-relaxed flex-1">{p.desc}</p>
              <div className={`mt-4 font-mono text-xs tracking-widest
                ${p.available ? "text-amber-tac cursor-pointer" : "text-text-muted"}`}>
                {p.cta}
              </div>
            </motion.div>
          ))}
        </div>
      </section>

      {/* CTA */}
      <section className="relative z-10 py-24 px-6 text-center border-t border-border-dim">
        <motion.div
          initial="hidden"
          whileInView="show"
          viewport={{ once: true }}
          variants={fade}
          custom={0}
        >
          <div className="font-mono text-xs text-text-muted tracking-[0.5em] uppercase mb-4">
            Mission ready
          </div>
          <h2 className="font-mono text-2xl font-bold text-white mb-8">
            Authorize your <span className="text-amber-tac">command deck.</span>
          </h2>
          <button
            onClick={() => loginWithRedirect()}
            className="btn-amber-fill"
          >
            Authorize Access →
          </button>
        </motion.div>
      </section>

      {/* Footer */}
      <footer className="relative z-10 border-t border-border-dim px-6 sm:px-12 py-6 flex items-center justify-between">
        <span className="font-mono text-xs text-text-muted tracking-widest">AUTONOMOUS MISSION CONTROL VICTORIA</span>
        <a
          href="https://github.com/diogobaltazar/TopGun"
          target="_blank"
          rel="noreferrer"
          className="font-mono text-xs text-text-muted hover:text-amber-tac transition-colors"
        >
          GitHub ↗
        </a>
      </footer>
    </div>
  );
}
