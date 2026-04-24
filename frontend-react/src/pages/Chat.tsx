import { useState, useEffect, useRef } from "react"
import Sidebar from "@/components/layout/Sidebar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Send, Loader2, Bot, User as UserIcon, Sparkles } from "lucide-react"
import api from "@/api/api"
import ReactMarkdown from "react-markdown"
import { toast } from "sonner"
import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip as ChartTooltip } from "recharts"

interface Message {
  role: "user" | "assistant"
  content: string
  display_type?: string
  data?: any
}

export default function Chat() {
  const [messages, setMessages] = useState<Message[]>([])
  const [input, setInput] = useState("")
  const [loading, setLoading] = useState(false)
  const [activeConvId, setActiveConvId] = useState<string | undefined>()
  const scrollRef = useRef<HTMLDivElement>(null)
  const [projectName, setProjectName] = useState("Projet")

  useEffect(() => {
    const userData = localStorage.getItem("pm_user")
    const activePid = localStorage.getItem("pm_active_project")
    if (userData && activePid) {
      const user = JSON.parse(userData)
      const proj = user.authorized_projects?.find((p: any) => p.identifier === activePid)
      if (proj) setProjectName(proj.name)
    }

    const alertInterval = setInterval(fetchAlerts, 60000)
    fetchAlerts()

    return () => clearInterval(alertInterval)
  }, [])

  const fetchAlerts = async () => {
    const pid = localStorage.getItem("pm_active_project")
    if (!pid) return
    try {
      const res = await api.get(`/alerts/${pid}`)
      const alerts = res.data.alerts || []
      alerts.forEach((alert: any) => {
        if (alert.level === "critique") {
          toast.error(alert.message)
        } else {
          toast.warning(alert.message)
        }
      })
    } catch (e) {
      console.error("Erreur alertes", e)
    }
  }

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }, [messages])

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!input.trim() || loading) return

    const activeProject = localStorage.getItem("pm_active_project")
    if (!activeProject) {
      toast.error("Veuillez sélectionner un projet dans la barre latérale.")
      return
    }

    const userMessage: Message = { role: "user", content: input }
    setMessages(prev => [...prev, userMessage])
    setInput("")
    setLoading(true)

    try {
      const response = await api.post("/chat", {
        question: input,
        project_id: activeProject,
        project_name: projectName,
        conversation_id: activeConvId,
        history: messages.slice(-5)
      })

      const botMessage: Message = { 
        role: "assistant", 
        content: response.data.answer || response.data.final_answer,
        display_type: response.data.display_type,
        data: response.data.data
      }
      setMessages(prev => [...prev, botMessage])
      
      if (response.data.conversation_id && !activeConvId) {
        setActiveConvId(response.data.conversation_id)
      }
    } catch (err) {
      setMessages(prev => [...prev, { role: "assistant", content: "Désolé, une erreur est survenue lors de la communication avec l'assistant." }])
    } finally {
      setLoading(false)
    }
  }

  const handleSelectConv = async (id: string) => {
    const activeProject = localStorage.getItem("pm_active_project")
    if (!activeProject) return

    setActiveConvId(id)
    setMessages([])
    setLoading(true)
    try {
      // La route correcte est /history/{project_id}?conversation_id={id}
      const response = await api.get(`/history/${activeProject}`, {
        params: { conversation_id: id }
      })
      setMessages(response.data.history || [])
    } catch (err) {
      console.error("Erreur historique", err)
      toast.error("Impossible de charger l'historique.")
    } finally {
      setLoading(false)
    }
  }

  const handleNewChat = () => {
    setActiveConvId(undefined)
    setMessages([])
  }

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      <Sidebar 
        activeConvId={activeConvId} 
        onSelectConv={handleSelectConv}
        onNewChat={handleNewChat}
      />

      <main className="flex-1 flex flex-col relative">
        <header className="h-16 border-b border-white/5 flex items-center justify-between px-8 bg-slate-950/50 backdrop-blur-md sticky top-0 z-10">
          <div className="flex flex-col">
            <div className="flex items-center gap-2">
               <Sparkles className="w-4 h-4 text-primary" />
               <h2 className="font-bold text-md bg-gradient-to-r from-white to-slate-400 bg-clip-text text-transparent">PM Assistant</h2>
            </div>
            <div className="text-[10px] text-slate-500 font-bold uppercase tracking-tighter">Projet : <span className="text-primary/80">{projectName}</span></div>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 bg-white/5 border border-white/10 px-3 py-1.5 rounded-full">
              <div className="w-2 h-2 rounded-full bg-emerald-500 shadow-[0_0_8px_#10b981] animate-pulse" />
              <span className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Système Actif</span>
            </div>
          </div>
        </header>

        <ScrollArea className="flex-1 p-4 md:p-8">
          <div className="max-w-3xl mx-auto space-y-8">
            {messages.length === 0 && !loading && (
              <div className="flex flex-col items-center justify-center h-[60vh] text-center space-y-4 animate-in fade-in zoom-in duration-500">
                <div className="w-20 h-20 bg-primary/10 rounded-3xl flex items-center justify-center mb-4 border border-primary/20 shadow-2xl shadow-primary/20 rotate-3">
                  <Bot className="w-10 h-10 text-primary" />
                </div>
                <h1 className="text-4xl font-black text-white tracking-tighter">Prêt pour l'analyse ?</h1>
                <p className="text-slate-400 max-w-sm leading-relaxed text-sm">
                  Sélectionnez un projet et posez vos questions. Je synchronise les données Redmine en temps réel.
                </p>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-4 animate-in slide-in-from-bottom-4 duration-500 ${msg.role === "assistant" ? "bg-white/[0.03] p-6 rounded-3xl border border-white/5 shadow-xl" : "px-6"}`}>
                <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 shadow-lg ${
                  msg.role === "assistant" ? "bg-primary text-primary-foreground" : "bg-slate-800 text-slate-400 border border-white/5"
                }`}>
                  {msg.role === "assistant" ? <Bot className="w-5 h-5" /> : <UserIcon className="w-5 h-5" />}
                </div>
                <div className="flex-1 space-y-3 overflow-hidden">
                  <div className="font-black text-[9px] text-slate-500 uppercase tracking-[0.2em]">
                    {msg.role === "assistant" ? "Assistant Intelligence" : "Chef de Projet"}
                  </div>
                  <div className="text-slate-200 leading-relaxed prose prose-invert prose-sm max-w-none">
                    <ReactMarkdown>{msg.content}</ReactMarkdown>
                  </div>
                  
                  {msg.display_type === "workload" && msg.data && (
                    <div className="mt-4 h-48 bg-slate-900/50 rounded-xl p-4 border border-white/5">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={Object.entries(msg.data.time_by_user || {}).map(([user, time]) => ({ user, time: Number(time) }))} layout="vertical">
                           <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" horizontal={false} />
                           <XAxis type="number" hide />
                           <YAxis dataKey="user" type="category" stroke="#64748b" fontSize={10} width={80} />
                           <ChartTooltip contentStyle={{ backgroundColor: "#0f172a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "8px" }} />
                           <Bar dataKey="time" fill="#6366f1" radius={[0, 4, 4, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  )}
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex gap-4 bg-white/[0.03] p-6 rounded-3xl border border-white/5 animate-pulse">
                <div className="w-9 h-9 bg-primary/20 rounded-xl flex items-center justify-center">
                  <Loader2 className="w-5 h-5 text-primary animate-spin" />
                </div>
                <div className="flex-1 space-y-3">
                  <div className="h-2 bg-white/10 rounded w-24"></div>
                  <div className="space-y-2">
                    <div className="h-2 bg-white/10 rounded w-full"></div>
                    <div className="h-2 bg-white/10 rounded w-4/5"></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={scrollRef} />
          </div>
        </ScrollArea>

        <div className="p-6 md:p-10 pt-0">
          <form 
            onSubmit={handleSendMessage}
            className="max-w-3xl mx-auto relative group"
          >
            <Input 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder={`Interroger l'assistant sur ${projectName}...`}
              className="w-full h-16 pl-8 pr-20 bg-slate-900/80 backdrop-blur-xl border-white/10 focus:border-primary/50 text-md rounded-3xl shadow-2xl transition-all font-sans"
              disabled={loading}
            />
            <Button 
              type="submit" 
              size="icon" 
              className="absolute right-3 top-3 h-10 w-10 rounded-2xl bg-primary hover:bg-primary/90 shadow-xl"
              disabled={loading || !input.trim()}
            >
              {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
            </Button>
          </form>
        </div>
      </main>
    </div>
  )
}
