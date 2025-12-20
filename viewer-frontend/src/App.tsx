import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { Layout } from '@/components/Layout'
import { Dashboard } from '@/pages/Dashboard'
import { Downloads } from '@/pages/Downloads'
import { Players } from '@/pages/Players'
import { Games } from '@/pages/Games'
import { Validation } from '@/pages/Validation'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="downloads" element={<Downloads />} />
          <Route path="players" element={<Players />} />
          <Route path="games" element={<Games />} />
          <Route path="validation" element={<Validation />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
