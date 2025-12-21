import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { Downloads } from '@/pages/Downloads'
import { Players } from '@/pages/Players'
import { PlayerDetail } from '@/pages/PlayerDetail'
import { Games } from '@/pages/Games'
import { GameDetail } from '@/pages/GameDetail'
import { Teams } from '@/pages/Teams'
import { TeamDetail } from '@/pages/TeamDetail'
import { Validation } from '@/pages/Validation'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="downloads" element={<Downloads />} />
          <Route path="players" element={<Players />} />
          <Route path="players/:playerId" element={<PlayerDetail />} />
          <Route path="games" element={<Games />} />
          <Route path="games/:gameId" element={<GameDetail />} />
          <Route path="teams" element={<Teams />} />
          <Route path="teams/:teamId" element={<TeamDetail />} />
          <Route path="validation" element={<Validation />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
