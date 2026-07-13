import { Octagon } from 'lucide-react'
import { useJobs } from '../context/JobsContext'

export default function StopBar() {
  const { activeCount, stopAll } = useJobs()

  if (activeCount === 0) return null

  return (
    <div className="fixed bottom-0 inset-x-0 z-50 flex justify-center pointer-events-none pb-4 px-4">
      <button
        type="button"
        onClick={stopAll}
        className="pointer-events-auto flex items-center gap-2 px-4 py-2.5 rounded-full bg-slate-900 text-white text-sm font-medium shadow-lg hover:bg-slate-800 transition-colors"
      >
        <Octagon className="w-4 h-4" />
        Stop all functions
      </button>
    </div>
  )
}
