import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card"
import { LogIn, Loader2 } from "lucide-react"
import api from "@/api/api"
import Cookies from "js-cookie"

export default function Login() {
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState("")
  const navigate = useNavigate()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError("")

    try {
      // Le backend attend un JSON avec "login" et "password"
      const response = await api.post("/auth/login", {
        login: username,
        password: password
      })

      if (response.data.access_token) {
        Cookies.set("pm_chatbot_access_token", response.data.access_token, { expires: 1 })
        // Optionnel: stocker le refresh_token et les infos user
        Cookies.set("pm_chatbot_refresh_token", response.data.refresh_token, { expires: 7 })
        localStorage.setItem("pm_user", JSON.stringify(response.data.user))
        
        navigate("/chat")
      }
    } catch (err: any) {
      setError(err.response?.data?.detail || "Erreur de connexion. Vérifiez vos identifiants.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-950 p-4">
      <Card className="w-full max-w-md bg-slate-900 border-white/10 shadow-2xl">
        <CardHeader className="space-y-1 text-center">
          <CardTitle className="text-3xl font-extrabold tracking-tight text-white">Connexion</CardTitle>
          <CardDescription className="text-slate-400">
            Entrez vos identifiants Redmine pour accéder à l'assistant.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2">
              <Input 
                placeholder="Identifiant Redmine" 
                className="bg-slate-800 border-white/5 text-white h-12"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                required
              />
            </div>
            <div className="space-y-2">
              <Input 
                type="password" 
                placeholder="Mot de passe" 
                className="bg-slate-800 border-white/5 text-white h-12"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
            </div>
            {error && <p className="text-red-400 text-sm text-center font-medium">{error}</p>}
            <Button type="submit" className="w-full h-12 text-md font-bold bg-primary hover:bg-primary/90" disabled={loading}>
              {loading ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <LogIn className="mr-2 h-5 w-5" />}
              Se connecter
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  )
}
