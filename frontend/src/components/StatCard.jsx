import { useEffect, useRef, useState } from 'react'
import { motion, useInView, useMotionValue, useSpring } from 'framer-motion'

function AnimatedNumber({ value }) {
  const ref = useRef(null)
  const inView = useInView(ref, { once: true })
  const motionVal = useMotionValue(0)
  const spring = useSpring(motionVal, { stiffness: 80, damping: 18 })
  const [display, setDisplay] = useState(0)

  useEffect(() => {
    if (inView && typeof value === 'number') {
      motionVal.set(value)
    }
  }, [inView, value, motionVal])

  useEffect(() => {
    return spring.on('change', v => setDisplay(Math.round(v)))
  }, [spring])

  if (typeof value !== 'number') return <span ref={ref}>{value ?? '—'}</span>
  return <span ref={ref}>{display}</span>
}

export default function StatCard({ label, value, sub, accent = false, index = 0 }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: 24 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.45, delay: index * 0.07, ease: [0.22, 1, 0.36, 1] }}
      whileHover={{
        y: -3,
        boxShadow: '0 8px 24px rgba(19,20,14,0.10)',
        backgroundColor: accent ? 'rgba(131,130,54,0.06)' : 'rgba(212,208,197,0.45)',
      }}
      className={`bg-white rounded-lg p-4 border cursor-default transition-colors ${accent ? 'border-olive/40' : 'border-bone-2'}`}
    >
      <p className="font-mono text-[9px] tracking-widest uppercase text-onyx-dim mb-1.5">{label}</p>
      <p className={`font-serif text-3xl font-bold leading-none ${accent ? 'text-olive' : 'text-onyx'}`}>
        <AnimatedNumber value={value} />
      </p>
      {sub && <p className="font-mono text-[10px] text-onyx-dim mt-1.5">{sub}</p>}
    </motion.div>
  )
}
