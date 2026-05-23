import { motion, AnimatePresence } from "framer-motion";

interface ProcessingStepsProps {
  steps: string[];
  currentIndex: number;
}

export default function ProcessingSteps({ steps, currentIndex }: ProcessingStepsProps) {
  const safeIndex  = Math.min(Math.max(currentIndex, 0), steps.length - 1);
  const label      = steps[safeIndex] ?? "";
  const isDone     = safeIndex === steps.length - 1;

  return (
    <div
      style={{
        width: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        gap: 36,
      }}
    >
      {/* ── Active rotating step ── */}
      <div
        style={{
          position: "relative",
          height: 72,
          width: "100%",
          maxWidth: 440,
          overflow: "hidden",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
        }}
      >
        <AnimatePresence mode="wait">
          <motion.div
            key={safeIndex}
            initial={{ opacity: 0, y: 48 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -48 }}
            transition={{
              duration: 0.5,
              ease: [0.22, 1, 0.36, 1],
            }}
            style={{
              position: "absolute",
              display: "flex",
              alignItems: "center",
              gap: 18,
            }}
          >
            {/* Spinner or final checkmark */}
            {isDone ? (
              <motion.div
                initial={{ scale: 0 }}
                animate={{ scale: 1 }}
                transition={{ type: "spring", stiffness: 420, damping: 20 }}
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: "50%",
                  background: "#2563eb",
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                  flexShrink: 0,
                }}
              >
                <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
                  <motion.path
                    d="M4 10 L8.5 14.5 L16 6"
                    stroke="white"
                    strokeWidth="2.5"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    initial={{ pathLength: 0 }}
                    animate={{ pathLength: 1 }}
                    transition={{ duration: 0.4, delay: 0.15 }}
                  />
                </svg>
              </motion.div>
            ) : (
              <motion.div
                animate={{ rotate: 360 }}
                transition={{ duration: 0.85, repeat: Infinity, ease: "linear" }}
                style={{
                  width: 44,
                  height: 44,
                  borderRadius: "50%",
                  border: "3.5px solid rgba(37, 99, 235, 0.12)",
                  borderTopColor: "#2563eb",
                  flexShrink: 0,
                }}
              />
            )}

            <span
              style={{
                fontSize: "22px",
                fontWeight: 700,
                color: "#1e3a8a",
                letterSpacing: "-0.025em",
                lineHeight: 1.3,
                fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
                whiteSpace: "nowrap",
              }}
            >
              {label}{!isDone ? "..." : ""}
            </span>
          </motion.div>
        </AnimatePresence>
      </div>

      {/* ── Progress bar ── */}
      <div
        style={{
          width: "100%",
          maxWidth: 400,
          height: 4,
          borderRadius: 99,
          background: "rgba(37, 99, 235, 0.1)",
          overflow: "hidden",
        }}
      >
        <motion.div
          animate={{ width: `${((safeIndex) / (steps.length - 1)) * 100}%` }}
          transition={{ duration: 0.6, ease: "easeOut" }}
          style={{
            height: "100%",
            borderRadius: 99,
            background: "linear-gradient(90deg, #3b82f6, #2563eb)",
          }}
        />
      </div>

      {/* ── Step counter ── */}
      <span
        style={{
          fontSize: 12,
          color: "rgba(37, 99, 235, 0.45)",
          fontFamily: "Inter, ui-sans-serif, system-ui, sans-serif",
          letterSpacing: "0.04em",
          marginTop: -20,
        }}
      >
        {safeIndex + 1} of {steps.length}
      </span>
    </div>
  );
}
