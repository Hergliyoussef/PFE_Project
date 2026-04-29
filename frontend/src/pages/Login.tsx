import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Loader2, Lock, User, ShieldCheck, Eye, EyeOff } from "lucide-react"
import api from "@/api/api"
import Cookies from "js-cookie"
import { toast } from "sonner"

export default function Login() {
  const [login, setLogin] = useState("")
  const [password, setPassword] = useState("")
  const [showPassword, setShowPassword] = useState(false)
  const [loading, setLoading] = useState(false)
  const navigate = useNavigate()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!login || !password) {
      toast.error("Veuillez remplir tous les champs.")
      return
    }

    setLoading(true)
    try {
      const response = await api.post("/auth/login", { login, password })
      
      const { access_token, user } = response.data
      
      // Stockage sécurisé
      // Stockage sécurisé
      Cookies.set("pm_chatbot_access_token", access_token, { expires: 1/24 }) // 1h
      localStorage.removeItem("pm_last_conv_id") // Reset chat pour le nouvel utilisateur
      localStorage.setItem("pm_user", JSON.stringify(user))
      
      if (user.authorized_projects?.length > 0) {
        localStorage.setItem("pm_active_project", user.authorized_projects[0].identifier)
      } else {
        localStorage.removeItem("pm_active_project")
      }

      toast.success(`Bienvenue, ${user.firstname} !`)
      navigate("/chat")
    } catch (err: any) {
      const status = err.response?.status
      if (status === 401) toast.error("Identifiant ou mot de passe incorrect.")
      else if (status === 403) toast.error(err.response?.data?.detail || "Accès réservé.")
      else toast.error("Erreur de connexion au serveur.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-[#0b0f1a] flex items-center justify-center p-12 overflow-hidden relative">
      {/* Background Orbs - Softer & More Diffused */}
      <div className="absolute top-[-10%] left-[-10%] w-[50%] h-[50%] bg-primary/5 rounded-full blur-[160px]" />
      <div className="absolute bottom-[-10%] right-[-10%] w-[50%] h-[50%] bg-purple-500/5 rounded-full blur-[160px]" />

      <div className="w-full max-w-[450px] space-y-4 animate-fade-in-up transform scale-100 origin-center">
        {/* Animated Logo Section */}
        <div className="text-center space-y-4">
          <div className="relative w-20 h-20 mx-auto mb-8">
            <div className="pulse-ring border-2 border-primary/40" />
            <div className="pulse-ring border-2 border-purple-500/25 [animation-delay:1.25s]" />
            <div className="relative z-10 w-20 h-20 bg-gradient-to-br from-primary/25 to-purple-500/20 border border-primary/35 rounded-[24px] flex items-center justify-center text-3xl shadow-2xl shadow-primary/15 animate-float">
              🤖
            </div>
          </div>

          <div className="space-y-1">
            <h1 className="text-3xl font-black tracking-tighter animate-grad bg-gradient-to-r from-white via-indigo-300 to-purple-400 bg-clip-text text-transparent">
              PM Assistant
            </h1>
            <p className="text-slate-200 text-[15px] font-bold uppercase tracking-[0.2em]">
              Chatbot IA d'Assistance à la Gestion de Projet
            </p>
          </div>
        </div>

        {/* Login Card */}
        <div className="bg-slate-900/40 backdrop-blur-xl border border-white/10 rounded-2xl p-6 shadow-2xl relative overflow-hidden">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-primary to-purple-500 opacity-50" />

          <div className="mb-6">
            <h2 className="text-lg font-bold text-white mb-2">Connexion</h2>
            <p className="text-slate-400 text-[17px]">Utilisez vos identifiants Redmine</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-2.5">
            <div className="space-y-0.5">
              <label className="text-[11px] font-bold text-slate-500 uppercase tracking-widest ml-1">Identifiant</label>
              <div className="relative group">
                <User className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 group-focus-within:text-primary transition-colors" strokeWidth={2.5} />
                <Input
                  value={login}
                  onChange={(e) => setLogin(e.target.value)}
                  placeholder="votre.identifiant"
                  className="bg-slate-950/50 border-white/10 focus:border-primary/50 h-11 pl-12 rounded-xl transition-all text-sm"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-[11px] font-bold text-slate-500 uppercase tracking-widest ml-1">Mot de passe</label>
              <div className="relative group">
                <Lock className="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500 group-focus-within:text-primary transition-colors" strokeWidth={2.5} />
                <Input
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  className="bg-slate-950/50 border-white/10 focus:border-primary/50 h-11 pl-12 pr-12 rounded-xl transition-all text-sm"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute right-4 top-1/2 -translate-y-1/2 text-black hover:text-slate-700 transition-colors"
                >
                  {showPassword ? <EyeOff className="w-4 h-4" strokeWidth={2.5} /> : <Eye className="w-4 h-4" strokeWidth={2.5} />}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full h-11 bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-500 hover:to-purple-500 text-white font-bold rounded-xl shadow-xl shadow-indigo-500/20 shine-effect animate-grad mt-2"
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : "🔓 Se connecter"}
            </Button>
          </form>
        </div>

        {/* Footer Info */}
        <div className="bg-indigo-500/5 border border-indigo-500/15 rounded-2xl p-4 text-center space-y-2">
          <div className="flex items-center justify-center gap-2 text-[11px] font-bold text-slate-400 uppercase tracking-wider">
            <ShieldCheck className="w-3 h-3 text-indigo-400" strokeWidth={2.5} />
            Accès réservé aux Chefs de projet & CEO uniquement
          </div>
          <p className="text-[10px] text-slate-600 font-medium">
            élaboré par Hergli Youssef - PFE/2026
          </p>
        </div>
      </div>
    </div>
  )
}
