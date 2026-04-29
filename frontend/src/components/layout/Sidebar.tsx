import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Plus, MessageSquare, Trash2, LogOut, FolderKanban, LayoutDashboard, ShieldCheck } from "lucide-react"
import api from "@/api/api"
import Cookies from "js-cookie"
import { useNavigate } from "react-router-dom"
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select"
import { Avatar, AvatarFallback } from "@/components/ui/avatar"

interface Conversation {
  id: string
  title: string
  created_at: string
  project_id: string
}

interface Project {
  id: number
  name: string
  identifier: string
}

interface UserData {
  firstname: string
  lastname: string
  roles?: string[]
  role?: string
  login: string
}

export default function Sidebar({
  activeConvId,
  onSelectConv,
  onNewChat
}: {
  activeConvId?: string,
  onSelectConv: (id: string) => void,
  onNewChat: () => void
}) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [projects, setProjects] = useState<Project[]>([])
  const [activeProject, setActiveProject] = useState<string>("")
  const [user, setUser] = useState<UserData | null>(null)
  const navigate = useNavigate()

  useEffect(() => {
    const userDataStr = localStorage.getItem("pm_user")
    if (userDataStr) {
      try {
        const userData = JSON.parse(userDataStr)
        console.log("DEBUG USER DATA:", userData)
        setUser(userData)
        const userProjects = userData.authorized_projects || []
        setProjects(userProjects)
        if (userProjects.length > 0) {
          const defaultProj = localStorage.getItem("pm_active_project") || userProjects[0].identifier
          setActiveProject(defaultProj)
        }
      } catch (e) {
        console.error("Erreur parsing user data", e)
      }
    }
  }, [])

  useEffect(() => {
    fetchConversations()
    const interval = setInterval(fetchConversations, 30000)
    return () => clearInterval(interval)
  }, [activeProject, activeConvId])

  const fetchConversations = async () => {
    try {
      const response = await api.get("/conversations")
      setConversations(response.data.conversations || [])
    } catch (err) {
      console.error("Erreur lors du chargement des conversations", err)
    }
  }

  const handleDelete = async (e: React.MouseEvent, id: string) => {
    e.stopPropagation()
    if (!confirm("Supprimer cette discussion ?")) return
    try {
      await api.delete(`/conversations/${id}`)
      setConversations(prev => prev.filter(c => c.id !== id))
      if (activeConvId === id) onNewChat()
    } catch (err) {
      alert("Erreur lors de la suppression")
    }
  }

  const handleLogout = () => {
    Cookies.remove("pm_chatbot_access_token")
    localStorage.removeItem("pm_user")
    localStorage.removeItem("pm_active_project")
    localStorage.removeItem("pm_last_conv_id")
    navigate("/login")
  }

  const handleProjectChange = (value: string) => {
    setActiveProject(value)
    localStorage.setItem("pm_active_project", value)
    onNewChat()
  }

  const filteredConversations = conversations.filter(c => c.project_id === activeProject)

  // Détection du rôle CEO
  const checkIsCEO = () => {
    if (!user) return false;
    const CEO_ALIASES = ['CEO', 'ADMINISTRATOR', 'ADMIN'];
    const hasCeoInList = user.roles?.some(r => CEO_ALIASES.some(alias => r.toUpperCase().includes(alias)));
    const hasCeoInField = user.role ? CEO_ALIASES.some(alias => user.role!.toUpperCase().includes(alias)) : false;
    return !!(hasCeoInList || hasCeoInField);
  }

  const isCEO = checkIsCEO();

  return (
    <div className="w-72 h-screen bg-[#0b0f1a] border-r border-white/5 flex flex-col">
      {/* Header & Projects */}
      <div className="p-4 space-y-4">
        <div className="flex items-center gap-2 px-2">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center font-bold text-primary-foreground shadow-lg shadow-primary/20">PM</div>
          <span className="font-bold text-slate-100 tracking-tight">Chatbot IA d'Assistance à la Gestion de Projet</span>
        </div>

        <div className="px-1">
          <Select value={activeProject} onValueChange={handleProjectChange}>
            <SelectTrigger className="w-full bg-white/5 border-white/10 text-slate-200 h-10">
              <div className="flex items-center gap-2 truncate">
                <FolderKanban className="w-4 h-4 text-primary shrink-0" strokeWidth={2.5} />
                <SelectValue placeholder="Sélectionner un projet" />
              </div>
            </SelectTrigger>
            <SelectContent className="bg-slate-900 border-white/10 text-slate-200">
              {projects.map((proj) => (
                <SelectItem key={proj.identifier} value={proj.identifier}>
                  {proj.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Button
          variant="outline"
          className="w-full justify-start gap-2 border-white/10 bg-primary/5 hover:bg-primary/10 text-primary border-primary/20 font-bold"
          onClick={onNewChat}
        >
          <Plus className="w-4 h-4" strokeWidth={2.5} />
          Nouvelle discussion
        </Button>
      </div>

      <Separator className="bg-white/5" />

      {/* History */}
      <div className="flex-1 overflow-hidden flex flex-col py-2">
        <div className="px-6 py-2 text-[10px] font-bold text-slate-500 uppercase tracking-widest">
          Discussions récentes
        </div>
        <ScrollArea className="flex-1 px-3">
          <div className="space-y-1">
            {filteredConversations.length > 0 ? filteredConversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => onSelectConv(conv.id)}
                role="button"
                className={`group w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all relative cursor-pointer ${activeConvId === conv.id
                    ? "bg-primary/10 text-primary font-bold"
                    : "text-slate-400 hover:bg-white/5 hover:text-slate-200"
                  }`}
              >
                <div className="relative shrink-0">
                  <MessageSquare className={`w-4 h-4 ${activeConvId === conv.id ? "text-primary" : "text-slate-500"}`} strokeWidth={2.5} />
                  <div className={`absolute -top-1 -right-1 w-2 h-2 rounded-full border-2 border-slate-950 ${activeConvId === conv.id
                      ? "bg-emerald-500 shadow-[0_0_5px_#10b981] animate-pulse"
                      : "bg-slate-700"
                    }`} />
                </div>
                <span className="truncate text-left pr-6">{conv.title || "Nouvelle discussion"}</span>

                <button
                  onClick={(e) => handleDelete(e, conv.id)}
                  className="absolute right-2 opacity-0 group-hover:opacity-100 p-1 rounded-md hover:bg-red-500/20 hover:text-red-400 transition-all z-10"
                >
                  <Trash2 className="w-3.5 h-3.5" strokeWidth={2.5} />
                </button>
              </div>
            )) : (
              <div className="px-6 py-8 text-center text-slate-600 text-xs italic leading-relaxed">
                Aucune discussion trouvée.
              </div>
            )}
          </div>
        </ScrollArea>
      </div>

      <Separator className="bg-white/5" />

      {/* Footer Navigation & Profile */}
      <div className="p-4 space-y-4">
        <div className="space-y-1">
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-slate-400 hover:text-slate-100 hover:bg-white/5 px-3 h-10 font-bold"
            onClick={() => navigate("/dashboard")}
          >
            <LayoutDashboard className="w-4 h-4" strokeWidth={2.5} />
            Tableau de Bord
          </Button>
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-red-400 hover:text-red-300 hover:bg-red-500/10 px-3 h-10 font-bold"
            onClick={handleLogout}
          >
            <LogOut className="w-4 h-4" strokeWidth={2.5} />
            Déconnexion
          </Button>
        </div>

        {/* User Profile Block */}
        {user && (
          <div className="bg-white/5 border border-white/10 rounded-2xl p-3 flex items-center gap-3">
            <Avatar className="w-10 h-10 border border-white/10">
              <AvatarFallback className="bg-primary/20 text-primary font-bold text-xs uppercase">
                {user.firstname?.[0]}{user.lastname?.[0]}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1 overflow-hidden">
              <div className="text-xs font-bold text-slate-100 truncate">
                {user.firstname} {user.lastname}
              </div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <ShieldCheck className={`w-3.5 h-3.5 ${isCEO ? "text-primary" : "text-slate-500"}`} strokeWidth={2.5} />
                <span className="text-[9px] font-black uppercase tracking-widest text-slate-500">
                  {isCEO ? "CEO" : "Project Manager"}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
