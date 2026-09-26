import { BrowserRouter, Outlet, Route, Routes } from 'react-router-dom'
import Navbar from './CommonComponents/Navbar/Navbar'
import Landing from './Pages/Landing/Landing'
import Chunk from './Pages/Chunk/Chunk'
import Retrieve from './Pages/Retrieve/Retrieve'
import Ask from './Pages/Ask/Ask'
import Evaluate from './Pages/Evaluate/Evaluate'

function Layout() {
  return (
    <>
      <Navbar />
      <Outlet />
    </>
  )
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<Landing />} />
          <Route path="/chunk" element={<Chunk />} />
          <Route path="/retrieve" element={<Retrieve />} />
          <Route path="/ask" element={<Ask />} />
          <Route path="/evaluate" element={<Evaluate />} />
        </Route>
      </Routes>
    </BrowserRouter>
  )
}

export default App
