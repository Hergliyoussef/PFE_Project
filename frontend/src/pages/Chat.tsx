import { useState, useEffect, useRef } from "react"
import Sidebar from "@/components/layout/Sidebar"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Send, Loader2, Bot, User as UserIcon, Sparkles, Command } from "lucide-react"
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
  const [activeConvId, setActiveConvId] = useState<string | undefined>(() => {
    return localStorage.getItem("pm_last_conv_id") || undefined
  })
  const scrollRef = useRef<HTMLDivElement>(null)
  const [projectName, setProjectName] = useState("Projet")

  useEffect(() => {
    const userData = localStorage.getItem("pm_user")
    const activePid = localStorage.getItem("pm_active_project")
    if (userData && activePid) {
      const user = JSON.parse(userData)
      const proj = user.authorized_projects?.find((p: any) => p.identifier === activePid)
      if (proj) setProjectName(proj.name)
      
      if (activeConvId) {
        handleSelectConv(activeConvId)
      }
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
        localStorage.setItem("pm_last_conv_id", response.data.conversation_id)
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
    localStorage.setItem("pm_last_conv_id", id)
    setMessages([])
    setLoading(true)
    try {
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
    localStorage.removeItem("pm_last_conv_id")
    setMessages([])
  }

  return (
    <div className="flex h-screen bg-[#0b0f1a] text-slate-100 overflow-hidden font-sans">
      <Sidebar 
        activeConvId={activeConvId} 
        onSelectConv={handleSelectConv}
        onNewChat={handleNewChat}
      />

      <main className="flex-1 flex flex-col relative bg-[radial-gradient(circle_at_50%_50%,rgba(99,102,241,0.02),transparent)]">
        {/* Floating Header */}
        <header className="h-16 border-b border-white/5 flex items-center justify-between px-8 bg-slate-950/40 backdrop-blur-2xl sticky top-0 z-20">
          <div className="flex flex-col">
            <div className="flex items-center gap-2.5">
               <div className="w-2 h-2 rounded-full bg-primary animate-pulse shadow-[0_0_8px_rgba(99,102,241,0.5)]" />
               <h2 className="font-black text-base tracking-tight text-white">Assistant IA</h2>
            </div>
            <div className="flex items-center gap-2 mt-0.5">
              <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Workspace:</span>
              <span className="text-[10px] font-bold text-primary/80 uppercase tracking-wider">{projectName}</span>
            </div>
          </div>
          <div className="flex items-center gap-4">
            {/* Indicateur de Vue */}
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border ${
              localStorage.getItem("pm_user") && (JSON.parse(localStorage.getItem("pm_user")!).roles?.some((r: string) => r.toUpperCase().includes("CEO")) || JSON.parse(localStorage.getItem("pm_user")!).role?.toUpperCase().includes("CEO"))
                ? "bg-primary/10 border-primary/20 text-primary"
                : "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
            }`}>
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse" />
              <span className="text-[10px] font-black uppercase tracking-[0.2em]">
                {localStorage.getItem("pm_user") && (JSON.parse(localStorage.getItem("pm_user")!).roles?.some((r: string) => r.toUpperCase().includes("CEO")) || JSON.parse(localStorage.getItem("pm_user")!).role?.toUpperCase().includes("CEO"))
                  ? "Vue CEO"
                  : "Vue Project Manager"
                }
              </span>
            </div>
          </div>
        </header>

        <ScrollArea className="flex-1 p-4 md:p-10">
          <div className="max-w-4xl mx-auto space-y-10">
            {messages.length === 0 && !loading && (
              <div className="flex flex-col items-center justify-center h-[65vh] text-center space-y-6 animate-in fade-in zoom-in duration-700">
                <div className="relative">
                  <div className="absolute inset-0 bg-primary/20 blur-3xl rounded-full" />
                  <div className="relative w-24 h-24 bg-gradient-to-br from-primary to-indigo-600 rounded-[32px] flex items-center justify-center mb-4 border border-white/10 shadow-2xl rotate-6 animate-float">
                    <Bot className="w-12 h-12 text-white" />
                  </div>
                </div>
                <div className="space-y-2">
                  <h1 className="text-4xl font-black text-white tracking-tighter sm:text-5xl">Analyse Intelligente</h1>
                  <p className="text-slate-400 max-w-sm mx-auto leading-relaxed text-base font-medium">
                    Posez vos questions sur le projet <span className="text-primary">{projectName}</span>. Je traite les données Redmine en temps réel.
                  </p>
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-5 animate-in slide-in-from-bottom-6 duration-500 ${msg.role === "assistant" ? "flex-row items-start" : "flex-row-reverse items-start"}`}>
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-2xl transition-transform hover:scale-105 ${
                  msg.role === "assistant" 
                    ? "bg-gradient-to-br from-primary to-indigo-600 text-white" 
                    : "bg-slate-800 text-slate-300 border border-white/10"
                }`}>
                  {msg.role === "assistant" ? <Bot className="w-5.5 h-5.5" /> : <UserIcon className="w-5.5 h-5.5" />}
                </div>
                
                <div className={`flex flex-col space-y-2 max-w-[85%] ${msg.role === "user" ? "items-end" : "items-start"}`}>
                  <div className="flex items-center gap-2 px-1">
                    <span className="font-black text-[9px] text-slate-500 uppercase tracking-[0.2em]">
                      {msg.role === "assistant" ? "Assistant" : "Utilisateur"}
                    </span>
                  </div>
                  
                  <div className={`px-6 py-4 rounded-[24px] shadow-2xl relative overflow-hidden transition-all hover:shadow-primary/5 ${
                    msg.role === "assistant" 
                      ? "bg-white/[0.04] backdrop-blur-xl border border-white/5 text-slate-200" 
                      : "bg-gradient-to-br from-indigo-600 to-primary text-white border border-white/10 rounded-tr-none"
                  }`}>
                    <div className="text-sm leading-relaxed prose prose-invert prose-p:my-0 prose-pre:bg-slate-950/50 prose-pre:border prose-pre:border-white/10 max-w-none">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                    
                    {msg.display_type === "workload" && msg.data && (
                      <div className="mt-5 h-52 bg-slate-950/40 rounded-2xl p-5 border border-white/5 shadow-inner">
                        <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={Object.entries(msg.data.time_by_user || {}).map(([user, time]) => ({ user, time: Number(time) }))} layout="vertical">
                             <CartesianGrid strokeDasharray="3 3" stroke="#ffffff05" horizontal={false} />
                             <XAxis type="number" hide />
                             <YAxis dataKey="user" type="category" stroke="#94a3b8" fontSize={10} width={85} tickLine={false} axisLine={false} />
                             <ChartTooltip contentStyle={{ backgroundColor: "#0f172a", border: "1px solid rgba(255,255,255,0.1)", borderRadius: "12px", boxShadow: "0 10px 30px rgba(0,0,0,0.5)" }} />
                             <Bar dataKey="time" fill="url(#colorBar)" radius={[0, 6, 6, 0]} />
                             <defs>
                               <linearGradient id="colorBar" x1="0" y1="0" x2="1" y2="0">
                                 <stop offset="0%" stopColor="#6366f1" />
                                 <stop offset="100%" stopColor="#8b5cf6" />
                               </linearGradient>
                             </defs>
                          </BarChart>
                        </ResponsiveContainer>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex gap-5 bg-white/[0.03] p-7 rounded-[32px] border border-white/5 animate-pulse">
                <div className="w-10 h-10 bg-primary/20 rounded-xl flex items-center justify-center">
                  <Loader2 className="w-5.5 h-5.5 text-primary animate-spin" />
                </div>
                <div className="flex-1 space-y-4">
                  <div className="h-2.5 bg-white/10 rounded-full w-28"></div>
                  <div className="space-y-3">
                    <div className="h-2.5 bg-white/10 rounded-full w-full"></div>
                    <div className="h-2.5 bg-white/10 rounded-full w-[90%]"></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={scrollRef} className="h-4" />
          </div>
        </ScrollArea>

        {/* Floating Input Bar */}
        <div className="p-6 md:p-10 pt-0 bg-gradient-to-t from-[#020617] via-[#020617]/90 to-transparent">
          <form 
            onSubmit={handleSendMessage}
            className="max-w-4xl mx-auto relative group"
          >
            <div className="absolute -inset-1 bg-gradient-to-r from-primary/20 to-indigo-600/20 rounded-[30px] blur opacity-0 group-focus-within:opacity-100 transition duration-500" />
            <div className="relative">
              <Input 
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={`Poser une question sur ${projectName}...`}
                className="w-full h-16 pl-8 pr-20 bg-slate-900/60 backdrop-blur-2xl border-white/10 focus:border-primary/40 text-base rounded-[28px] shadow-[0_20px_50px_rgba(0,0,0,0.4)] transition-all font-sans placeholder:text-slate-500 focus:ring-0"
                disabled={loading}
              />
              <Button 
                type="submit" 
                size="icon" 
                className="absolute right-3 top-3 h-10 w-10 rounded-[18px] bg-gradient-to-br from-red-600 to-rose-600 hover:scale-105 active:scale-95 transition-all shadow-xl shadow-red-500/20"
                disabled={loading || !input.trim()}
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
              </Button>
            </div>
          </form>
          <div className="text-center mt-4">
            <span className="text-[10px] font-bold text-slate-600 uppercase tracking-[0.3em]">IA Analyse &bull; Redmine Sync</span>
          </div>
        </div>
      </main>
    </div>
  )
}
