import { useState, useEffect } from "react"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Separator } from "@/components/ui/separator"
import { Plus, MessageSquare, Trash2, LogOut, FolderKanban, LayoutDashboard, ShieldCheck } from "lucide-react"
import { ThemeToggle } from "@/components/ui/theme-toggle"
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
  onNewChat,
  onProjectChange
}: {
  activeConvId?: string,
  onSelectConv: (id: string) => void,
  onNewChat: () => void,
  onProjectChange?: (projectId: string) => void
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
    if (onProjectChange) {
      onProjectChange(value)
    } else {
      onNewChat()
    }
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
    <div className="w-72 h-screen bg-slate-100 dark:bg-card border-r border-border flex flex-col transition-all duration-300">
      {/* Header & Projects */}
      <div className="p-4 space-y-4">
        <div className="flex items-center justify-between px-2 py-2">
          <div className="flex items-center gap-3">
            <div className="relative group">
              <div className="absolute inset-0 bg-primary/20 blur-xl rounded-full animate-pulse group-hover:bg-primary/40 transition-all duration-500" />
              <div className="relative w-12 h-12 bg-gradient-to-br from-primary to-emerald-600 rounded-[14px] flex items-center justify-center font-black text-primary-foreground shadow-2xl shadow-primary/30 border border-border animate-float">
                PM
              </div>
            </div>
            <div className="flex flex-col leading-tight">
              <span className="font-black text-foreground tracking-tight text-[13px]">Chatbot d'Assistance </span>
              <span className="text-[10px] font-bold text-muted-foreground uppercase tracking-widest">à la Gestion de Projet</span>
            </div>
          </div>
          <ThemeToggle />
        </div>

        <div className="px-1">
          <Select value={activeProject} onValueChange={handleProjectChange}>
            <SelectTrigger className="w-full bg-primary/10 border-primary/20 text-foreground h-12 rounded-2xl hover:bg-primary/20 transition-all shadow-lg shadow-primary/5">
              <div className="flex items-center gap-2.5 truncate">
                <div className="p-1.5 bg-primary/20 rounded-lg text-primary">
                  <FolderKanban className="w-4 h-4" strokeWidth={2.5} />
                </div>
                <div className="flex flex-col items-start truncate leading-tight">
                  <span className="text-[9px] font-black text-primary uppercase tracking-widest">Projet</span>
                  <SelectValue placeholder="Choisir un projet" className="font-bold text-xs text-foreground" />
                </div>
              </div>
            </SelectTrigger>
            <SelectContent className="bg-popover border-border text-popover-foreground rounded-2xl shadow-2xl">
              {projects.map((proj) => (
                <SelectItem key={proj.identifier} value={proj.identifier} className="rounded-xl focus:bg-primary/20 focus:text-primary">
                  {proj.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <Button
          variant="outline"
          className="w-full justify-start gap-2 border-border bg-primary/5 hover:bg-primary/10 text-primary font-bold"
          onClick={onNewChat}
        >
          <Plus className="w-4 h-4" strokeWidth={2.5} />
          Nouvelle discussion
        </Button>
      </div>

      <Separator className="bg-border" />

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
                    : "text-muted-foreground hover:bg-muted hover:text-foreground"
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

      <Separator className="bg-border" />

      {/* Footer Navigation & Profile */}
      <div className="p-4 space-y-4">
        <div className="space-y-1">
          <Button
            variant="ghost"
            className="w-full justify-start gap-3 text-muted-foreground hover:text-foreground hover:bg-muted px-3 h-10 font-bold"
            onClick={() => navigate(`/dashboard/${activeProject}`)}
          >
            <LayoutDashboard className="w-4 h-4" strokeWidth={2.5} />
            Tableau de Bord
          </Button>
          <div className="flex items-center gap-2 px-3">
            <Button
              variant="ghost"
              className="flex-1 justify-start gap-3 text-red-400 hover:text-red-300 hover:bg-red-500/10 h-10 font-bold"
              onClick={handleLogout}
            >
              <LogOut className="w-4 h-4" strokeWidth={2.5} />
              Déconnexion
            </Button>
          </div>
        </div>

        {/* User Profile Block */}
        {user && (
          <div className="bg-muted border border-border rounded-2xl p-3 flex items-center gap-3">
            <Avatar className="w-10 h-10 border border-white/10">
              <AvatarFallback className="bg-primary/20 text-primary font-bold text-xs uppercase">
                {user.firstname?.[0]}{user.lastname?.[0]}
              </AvatarFallback>
            </Avatar>
            <div className="flex-1 overflow-hidden">
              <div className="text-xs font-bold text-foreground truncate">
                {user.firstname} {user.lastname}
              </div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <ShieldCheck className={`w-3.5 h-3.5 ${isCEO ? "text-primary" : "text-slate-500"}`} strokeWidth={2.5} />
                <span className="text-[9px] font-black uppercase tracking-widest text-slate-500">
                  {isCEO ? "CEO" : "Chef de projet"}
                </span>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
