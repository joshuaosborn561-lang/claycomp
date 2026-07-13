import {
  createContext,
  useCallback,
  useContext,
  useRef,
  useState,
  type ReactNode,
} from 'react'

type JobsContextValue = {
  activeCount: number
  stopAll: () => void
  track: <T>(run: (signal: AbortSignal) => Promise<T>) => Promise<T>
}

const JobsContext = createContext<JobsContextValue | null>(null)

export function JobsProvider({ children }: { children: ReactNode }) {
  const controllers = useRef(new Set<AbortController>())
  const [activeCount, setActiveCount] = useState(0)

  const stopAll = useCallback(() => {
    for (const controller of controllers.current) controller.abort()
    controllers.current.clear()
    setActiveCount(0)
  }, [])

  const track = useCallback(async <T,>(run: (signal: AbortSignal) => Promise<T>): Promise<T> => {
    const controller = new AbortController()
    controllers.current.add(controller)
    setActiveCount((count) => count + 1)
    try {
      return await run(controller.signal)
    } finally {
      controllers.current.delete(controller)
      setActiveCount((count) => Math.max(0, count - 1))
    }
  }, [])

  return (
    <JobsContext.Provider value={{ activeCount, stopAll, track }}>
      {children}
    </JobsContext.Provider>
  )
}

export function useJobs() {
  const ctx = useContext(JobsContext)
  if (!ctx) throw new Error('useJobs must be used within JobsProvider')
  return ctx
}

export function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}
