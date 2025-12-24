import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { SeasonProvider } from '@/contexts/SeasonContext'
import { Layout } from '@/components/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { Downloads } from '@/pages/Downloads'
import { Coverage } from '@/pages/Coverage'
import { Players } from '@/pages/Players'
import { PlayerDetail } from '@/pages/PlayerDetail'
import { Games } from '@/pages/Games'
import { GameDetail } from '@/pages/GameDetail'
import { Teams } from '@/pages/Teams'
import { TeamDetail } from '@/pages/TeamDetail'
import { Validation } from '@/pages/Validation'
import { GameReconciliation } from '@/pages/GameReconciliation'
import { Lineups } from '@/pages/Lineups'
import { Injuries } from '@/pages/Injuries'
import { Help } from '@/pages/Help'

function App() {
  return (
    <BrowserRouter>
      <SeasonProvider>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="downloads" element={<Downloads />} />
            <Route path="coverage" element={<Coverage />} />
            <Route path="players" element={<Players />} />
            <Route path="players/:playerId" element={<PlayerDetail />} />
            <Route path="games" element={<Games />} />
            <Route path="games/:gameId" element={<GameDetail />} />
            <Route path="teams" element={<Teams />} />
            <Route path="teams/:teamId" element={<TeamDetail />} />
            <Route path="lineups" element={<Lineups />} />
            <Route path="injuries" element={<Injuries />} />
            <Route path="validation" element={<Validation />} />
            <Route path="validation/game/:gameId" element={<GameReconciliation />} />
            <Route path="help" element={<Help />} />
          </Route>
        </Routes>
      </SeasonProvider>
    </BrowserRouter>
  )
}

export default App
