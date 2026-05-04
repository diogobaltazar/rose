import { createContext, useContext, useState, useCallback, ReactNode } from "react";

export interface EngagedMission {
  uid: string;
  title: string;
  startedAt: Date;
}

interface Ctx {
  missions: EngagedMission[];
  engage: (uid: string, title: string) => void;
  abort: (uid: string) => void;
  isEngaged: (uid: string) => boolean;
}

const EngagementContext = createContext<Ctx | null>(null);

export function EngagementProvider({ children }: { children: ReactNode }) {
  const [missions, setMissions] = useState<EngagedMission[]>([]);

  const engage = useCallback((uid: string, title: string) => {
    setMissions(prev =>
      prev.find(m => m.uid === uid) ? prev : [...prev, { uid, title, startedAt: new Date() }]
    );
  }, []);

  const abort = useCallback((uid: string) => {
    setMissions(prev => prev.filter(m => m.uid !== uid));
  }, []);

  const isEngaged = useCallback((uid: string) => missions.some(m => m.uid === uid), [missions]);

  return (
    <EngagementContext.Provider value={{ missions, engage, abort, isEngaged }}>
      {children}
    </EngagementContext.Provider>
  );
}

export function useEngagement() {
  const ctx = useContext(EngagementContext);
  if (!ctx) throw new Error("useEngagement must be used within EngagementProvider");
  return ctx;
}
