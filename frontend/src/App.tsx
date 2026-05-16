import { BrowserRouter as Router, Routes, Route } from "react-router-dom"
import Home from "./pages/Home"
import Login from "./pages/Login"
import Chat from "./pages/Chat"
import Dashboard from "./pages/Dashboard"
import { Toaster } from "sonner"
import { ThemeProvider } from "./context/ThemeContext"

function App() {
  return (
    <ThemeProvider>
      <Toaster position="bottom-right" theme="system" richColors />
      <Router>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/login" element={<Login />} />
          <Route path="/chat" element={<Chat />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/dashboard/:projectId" element={<Dashboard />} />
        </Routes>
      </Router>
    </ThemeProvider>
  )
}

export default App
