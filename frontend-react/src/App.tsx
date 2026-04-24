import { BrowserRouter as Router, Routes, Route } from "react-router-dom"
import Home from "./pages/Home"
import Login from "./pages/Login"
import Chat from "./pages/Chat"
import Dashboard from "./pages/Dashboard"
import { Toaster } from "sonner"

function App() {
  return (
    <>
      <Toaster position="bottom-right" theme="dark" richColors />
      <Router>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/dashboard" element={<Dashboard />} />
        </Routes>
      </Router>
    </>
  )
}

export default App
