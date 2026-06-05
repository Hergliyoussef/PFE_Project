import { useState, useEffect, useRef, useMemo } from "react"
import Sidebar from "@/components/layout/Sidebar"
import { Button } from "@/components/ui/button"
import { ScrollArea } from "@/components/ui/scroll-area"
import { Send, Loader2, Bot, User as UserIcon, CheckCircle2, XCircle, AlertTriangle, Clock, Calendar, Shield, BarChart3, Trophy, Target, Zap, Trash2, X, Activity, Bell } from "lucide-react"
import axios from "axios"
import Cookies from "js-cookie"
import ReactMarkdown from "react-markdown"
import remarkGfm from "remark-gfm"
import { toast } from "sonner"

const API_BASE_URL = "/api/v1"

const getApi = () => {
  const token = Cookies.get("pm_chatbot_access_token")
  const instance = axios.create({
    baseURL: API_BASE_URL,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {})
    }
  })

  instance.interceptors.response.use(
    (response) => response,
    (error) => {
      const status = error.response?.status
      if (status === 401 || status === 403) {
        if (!window.location.pathname.includes("/login")) {
          Cookies.remove("pm_chatbot_access_token")
          localStorage.removeItem("pm_user")
          localStorage.removeItem("pm_active_project")
          localStorage.removeItem("pm_last_conv_id")
          window.location.href = "/login?expired=true"
        }
      }
      return Promise.reject(error)
    }
  )
  return instance
}

const api = {
  get: (url: string, config?: any) => getApi().get(url, config),
  post: (url: string, data?: any, config?: any) => getApi().post(url, data, config),
  put: (url: string, data?: any, config?: any) => getApi().put(url, data, config),
  delete: (url: string, config?: any) => getApi().delete(url, config),
}

const SprintTaskSelector = ({
  projectId,
  sprintName,
  onChange,
}: {
  projectId: string;
  sprintName: string;
  onChange: (ids: number[]) => void;
}) => {
  const [tasks, setTasks] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    const fetchTasks = async () => {
      try {
        setLoading(true);
        const res = await api.get(`/projects/${projectId}/sprint-tasks?sprint_name=${encodeURIComponent(sprintName)}`);
        if (active) {
          setTasks(res.data.tasks || []);
          // Envoyer l'état initial des tâches déjà dans le sprint
          const initialIds = (res.data.tasks || [])
            .filter((t: any) => t.in_sprint)
            .map((t: any) => t.id);
          onChange(initialIds);
          setError(null);
        }
      } catch (err: any) {
        if (active) {
          setError("Impossible de charger les tâches.");
        }
      } finally {
        if (active) {
          setLoading(false);
        }
      }
    };
    if (projectId && sprintName) {
      fetchTasks();
    } else {
      setLoading(false);
    }
    return () => {
      active = false;
    };
  }, [projectId, sprintName]);

  const handleToggle = (taskId: number) => {
    const updated = tasks.map((t) =>
      t.id === taskId ? { ...t, in_sprint: !t.in_sprint } : t
    );
    setTasks(updated);
    const selectedIds = updated.filter((t) => t.in_sprint).map((t) => t.id);
    onChange(selectedIds);
  };

  if (loading) {
    return (
      <div className="flex items-center gap-2 py-3 text-xs text-slate-400 font-sans">
        <Loader2 className="animate-spin h-3.5 w-3.5 text-primary" />
        Chargement des tâches...
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-xs text-red-400 py-2 font-sans">
        {error}
      </div>
    );
  }

  if (tasks.length === 0) {
    return (
      <div className="text-xs text-slate-500 py-2 italic font-sans">
        Aucune tâche trouvée dans ce projet.
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-1.5 mt-2 max-h-[220px] overflow-y-auto pr-1 font-sans scrollbar-thin scrollbar-thumb-white/10 scrollbar-track-transparent">
      {tasks.map((task) => (
        <label
          key={task.id}
          className={`flex items-start gap-3 p-2.5 rounded-lg border text-xs cursor-pointer transition-all ${
            task.in_sprint
              ? 'bg-primary/10 border-primary/30 text-white'
              : 'bg-slate-900/40 border-white/5 text-slate-400 hover:bg-slate-900/60 hover:text-slate-300'
          }`}
        >
          <input
            type="checkbox"
            checked={task.in_sprint}
            onChange={() => handleToggle(task.id)}
            className="mt-0.5 rounded border-white/10 bg-slate-900/50 text-primary focus:ring-0 focus:ring-offset-0 w-3.5 h-3.5 cursor-pointer"
          />
          <div className="flex flex-col flex-1 min-w-0">
            <span className="font-semibold truncate text-[11px]">#{task.id} - {task.subject}</span>
            <div className="flex items-center gap-2 mt-1">
              <span className="px-1.5 py-0.5 rounded text-[8px] bg-white/5 text-slate-400 border border-white/5">
                {task.status}
              </span>
              {task.other_sprint && !task.in_sprint && (
                <span className="text-[8px] text-amber-400 font-medium">
                  (Dans le sprint: {task.other_sprint})
                </span>
              )}
            </div>
          </div>
        </label>
      ))}
    </div>
  );
};

import { BarChart, Bar, XAxis, YAxis, CartesianGrid, ResponsiveContainer, Tooltip as ChartTooltip } from "recharts"

interface Message {
  id?: number
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
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const [projectName, setProjectName] = useState("Projet")
  const [activeAlerts, setActiveAlerts] = useState<any[]>([])
  const [popupAlerts, setPopupAlerts] = useState<any[]>([])
  const [showNotifications, setShowNotifications] = useState(false)
  const [activePid, setActivePid] = useState<string>(() => {
    return localStorage.getItem("pm_active_project") || ""
  })

  // Détection si l'utilisateur est un CEO pour écouter toutes les alertes globales
  const isUserCeo = useMemo(() => {
    const userData = localStorage.getItem("pm_user");
    if (!userData) return false;
    try {
      const u = JSON.parse(userData);
      return u.roles?.some((r: string) => r.toUpperCase().includes("CEO")) || u.role?.toUpperCase().includes("CEO") || u.is_admin;
    } catch {
      return false;
    }
  }, []);

  const authorizedProjectIds = useMemo(() => {
    const userDataStr = localStorage.getItem("pm_user");
    if (!userDataStr) return [];
    try {
      const user = JSON.parse(userDataStr);
      return user.authorized_projects?.map((p: any) => p.identifier) || [];
    } catch {
      return [];
    }
  }, []);

  const displayedAlerts = useMemo(() => {
    let alerts = activeAlerts;
    if (!isUserCeo) {
      alerts = activeAlerts.filter(a => authorizedProjectIds.includes(a.project_id));
    }
    // S'assurer que les plus récents (created_at le plus grand) sont en premier
    return [...alerts].sort((a, b) => (b.created_at || 0) - (a.created_at || 0));
  }, [activeAlerts, authorizedProjectIds, isUserCeo]);

  const displayedPopupAlerts = useMemo(() => {
    if (isUserCeo) return popupAlerts;
    return popupAlerts.filter(a => authorizedProjectIds.includes(a.project_id));
  }, [popupAlerts, authorizedProjectIds, isUserCeo]);

  // --- WebSocket pour Temps Réel ---
  useEffect(() => {
    const pid = activePid || localStorage.getItem("pm_active_project");
    if (!pid) return;

    // Tout le monde écoute le canal global "all_projects" pour le multi-projet en temps réel
    // Le filtrage sécurisé est géré côté front-end via les projets autorisés.
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.hostname}:8000/ws/dashboard/all_projects`;
    const socket = new WebSocket(wsUrl);

    socket.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data?.type === "new_alert") {
          const alertId = data.alert.id || (Date.now() + Math.random().toString());
          const newAlert = { ...data.alert, id: alertId };
          setActiveAlerts(prev => [newAlert, ...prev]);
          setPopupAlerts(prev => [newAlert, ...prev]);
          setTimeout(() => {
            setPopupAlerts(prev => prev.filter(a => a.id !== alertId));
          }, 7000);
        }
      } catch {}
    };
    return () => {
      if (socket.readyState === WebSocket.OPEN) {
        socket.close();
      } else if (socket.readyState === WebSocket.CONNECTING) {
        socket.addEventListener('open', () => socket.close());
      } else {
        socket.close();
      }
    };
  }, [activePid, isUserCeo]);

  const fetchAlerts = async () => {
    const activeProject = localStorage.getItem("pm_active_project")
    if (!activeProject) return
    try {
      const res = await api.get(`/alerts/${activeProject}`)
      setActiveAlerts(res.data.alerts || [])
    } catch (e) {
      console.error("Erreur lors de la récupération des alertes", e)
    }
  }

  const handleDismissAlert = async (alertId: string) => {
    const activeProject = localStorage.getItem("pm_active_project")
    if (!activeProject) return
    try {
      await api.delete(`/alerts/${activeProject}/${alertId}`)
      setActiveAlerts(prev => prev.filter(a => a.id !== alertId))
    } catch (e) {
      console.error("Erreur lors de la suppression de l'alerte", e)
      setActiveAlerts(prev => prev.filter(a => a.id !== alertId))
    }
  }

  const handleClearAllAlerts = async () => {
    const activeProject = localStorage.getItem("pm_active_project")
    if (!activeProject) return
    try {
      await api.delete(`/alerts/${activeProject}`)
      setActiveAlerts([])
    } catch (e) {
      console.error("Erreur lors de la suppression de toutes les alertes", e)
      setActiveAlerts([])
    }
  }

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
    fetchAlerts()
  }, [])

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollIntoView({ behavior: "smooth" })
    }
  }, [messages])

  useEffect(() => {
    if (textareaRef.current) {
      textareaRef.current.style.height = "auto"
      textareaRef.current.style.height = `${textareaRef.current.scrollHeight}px`
    }
  }, [input])

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if (!input.trim() || loading) return

    const activeProject = localStorage.getItem("pm_active_project")
    if (!activeProject) {
      toast.error("Veuillez sélectionner un projet dans la barre latérale.")
      return
    }

    const userMessage: Message = { role: "user", content: input }
    setInput("")
    setLoading(true)

    // On ajoute le message utilisateur et un message assistant vide
    setMessages(prev => [
      ...prev,
      userMessage,
      { role: "assistant", content: "", display_type: "text", data: {} }
    ]);

    try {
      const token = Cookies.get("pm_chatbot_access_token")
      const response = await fetch(`/api/v1/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          question: input,
          project_id: activeProject,
          project_name: projectName,
          conversation_id: activeConvId,
          history: messages.slice(-10)
        })
      });

      if (!response.body) throw new Error("Pas de corps de réponse");

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullContent = "";

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value);
        const lines = chunk.split("\n\n");

        for (const line of lines) {
          if (line.startsWith("data: ")) {
            const dataStr = line.replace("data: ", "").trim();
            if (dataStr === "[DONE]") continue;

            try {
              const parsed = JSON.parse(dataStr);
              
              if (parsed.conversation_id && !activeConvId) {
                setActiveConvId(parsed.conversation_id);
                localStorage.setItem("pm_last_conv_id", parsed.conversation_id);
              }

              if (parsed.event === 'messages_saved') {
                setMessages(prev => {
                  const newMsgs = [...prev];
                  if (newMsgs.length >= 2) {
                    newMsgs[newMsgs.length - 2].id = parsed.user_message_id;
                    newMsgs[newMsgs.length - 1].id = parsed.assistant_message_id;
                  }
                  return newMsgs;
                });
              }

              if (parsed.token) {
                fullContent += parsed.token;
                // Mise à jour du DERNIER message (celui qu'on vient d'ajouter)
                setMessages(prev => {
                  const newMsgs = [...prev];
                  if (newMsgs.length > 0) {
                    const lastIdx = newMsgs.length - 1;
                    newMsgs[lastIdx] = {
                      ...newMsgs[lastIdx],
                      content: fullContent,
                      display_type: parsed.intent === 'planning' ? 'action_confirmation' : 'text',
                      data: parsed.data || {}
                    };
                  }
                  return newMsgs;
                });
              }
            } catch (e) {
              console.error("Erreur parse chunk", e);
            }
          }
        }
      }
    } catch (err) {
      console.error("Erreur fatale stream:", err);
      toast.error("Erreur de communication avec l'assistant.");
    } finally {
      setLoading(false)
      window.dispatchEvent(new Event("refreshConversations"));
    }
  }

  const handleSelectConv = async (convId: string) => {
    const activeProject = localStorage.getItem("pm_active_project")
    if (!activeProject) return
    setActiveConvId(convId)
    localStorage.setItem("pm_last_conv_id", convId)
    setLoading(true)
    try {
      const res = await api.get(`/history/${activeProject}?conversation_id=${convId}`)
      setMessages(res.data.history || [])
    } catch (e) {
      console.error("Erreur historique", e)
      setMessages([])
      setActiveConvId(undefined)
      localStorage.removeItem("pm_last_conv_id")
      toast.error("Impossible de charger l'historique")
    } finally {
      setLoading(false)
    }
  }

  const handleDeleteMessage = async (msgId?: number) => {
    if (!msgId) return;
    try {
      await api.delete(`/messages/${msgId}`);
      setMessages(prev => prev.filter(m => m.id !== msgId));
      toast.success("Message supprimé");
    } catch (e) {
      console.error("Erreur suppression message", e);
      toast.error("Erreur lors de la suppression");
    }
  }

  const handleClearChat = async () => {
    if (!activeConvId) return;
    if (!confirm("Voulez-vous vraiment supprimer toute cette conversation ?")) return;
    try {
      await api.delete(`/conversations/${activeConvId}`);
      setMessages([]);
      setActiveConvId(undefined);
      localStorage.removeItem("pm_last_conv_id");
      toast.success("Conversation supprimée");
    } catch (e) {
      console.error("Erreur suppression conversation", e);
      toast.error("Erreur lors de la suppression");
    }
  }

  const handleNewChat = () => {
    setActiveConvId(undefined)
    localStorage.removeItem("pm_last_conv_id")
    setMessages([])
  }

  const handleProjectChange = (projectId: string) => {
    handleNewChat()
    setActivePid(projectId)

    // Update project name from local storage (Sidebar already updated it)
    const userDataStr = localStorage.getItem("pm_user")
    if (userDataStr) {
      const user = JSON.parse(userDataStr)
      const proj = user.authorized_projects?.find((p: any) => p.identifier === projectId)
      if (proj) setProjectName(proj.name)
    }

    // Clear alerts for new project and fetch new ones
    setActiveAlerts([])
    setTimeout(() => {
      fetchAlerts()
    }, 100)
  }

  const handleTaskExecution = async (actions: any[], msgIndex: number, accept: boolean) => {
    if (!accept) {
      setMessages(prev => {
        const newMessages = [...prev]
        newMessages[msgIndex] = { 
          ...newMessages[msgIndex], 
          content: "Opérations annulées par l'utilisateur.",
          display_type: "text" 
        }
        return newMessages
      })
      toast.info("Opérations annulées.")
      return
    }

    setLoading(true)
    try {
      // Exécution séquentielle des actions
      for (const action of actions) {
        await api.post("/execute-task", {
          action_type: action.action_type,
          parameters: action.parameters
        })
      }

      toast.success(`${actions.length} action(s) exécutée(s) avec succès !`)
      setMessages(prev => {
        const newMessages = [...prev]
        newMessages[msgIndex] = { 
          ...newMessages[msgIndex], 
          content: "Toutes les actions ont été validées et exécutées avec succès sur Redmine.",
          display_type: "text" 
        }
        return newMessages
      })
    } catch (e: any) {
      toast.error(e.response?.data?.detail || "Erreur lors de l'exécution des actions.")
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen bg-background text-foreground overflow-hidden font-sans relative">
      <Sidebar
        activeConvId={activeConvId}
        onSelectConv={handleSelectConv}
        onNewChat={handleNewChat}
        onProjectChange={handleProjectChange}
      />

      {/* Temporary Alert Popups (Toasts) - Placed at root level to ensure they stay at the top-right exactly like the Dashboard! */}
      <div className="fixed top-24 right-8 z-[150] flex flex-col gap-4 max-w-md pointer-events-auto">
        {displayedPopupAlerts.map((alert) => (
          <div 
            key={alert.id} 
            className={`p-4 rounded-2xl border shadow-2xl backdrop-blur-2xl animate-fade-in-right flex items-start gap-4 
              ${alert.level === 'critique' ? 'bg-red-500/10 border-red-500/20 text-red-400' : 'bg-amber-500/10 border-amber-500/20 text-amber-400'}`}
          >
            <div className={`p-2 rounded-lg ${alert.level === 'critique' ? 'bg-red-500/20' : 'bg-amber-500/20'}`}>
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div className="flex-1 space-y-1">
              <div className="flex flex-wrap items-center gap-1.5">
                <span className="text-[10px] font-black uppercase tracking-widest opacity-70">Alerte IA {alert.type}</span>
                {alert.project_name && (
                  <span className="px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-widest bg-slate-800 text-emerald-400 border border-emerald-500/10">
                    {alert.project_name}
                  </span>
                )}
              </div>
              <p className="text-xs font-bold leading-relaxed text-white">{alert.message}</p>
            </div>
            <button 
              onClick={() => setPopupAlerts(prev => prev.filter(a => a.id !== alert.id))}
              className="text-white/20 hover:text-white transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>

      <main className="flex-1 flex flex-col relative bg-[radial-gradient(circle_at_50%_50%,rgba(99,102,241,0.02),transparent)]">
        {/* Floating Header */}
        <header className="h-16 border-b border-border flex items-center justify-between px-8 bg-slate-100/80 dark:bg-slate-950/80 backdrop-blur-2xl sticky top-0 z-20 animate-fade-in transition-all duration-300">
          <div className="flex items-center gap-6">
            <div className="flex flex-col">
              <div className="flex items-center gap-2">
                <Bot className="w-5 h-5 text-primary animate-pulse" />
                <h2 className="font-black text-sm uppercase tracking-wider text-foreground">Chatbot-PFE-Hergli</h2>
              </div>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="text-[9px] font-black text-slate-500 uppercase tracking-widest">Projet :</span>
                <span className="text-[10px] font-bold text-primary/80 uppercase tracking-wider">{projectName || "Sélectionner un projet"}</span>
              </div>
            </div>

            {/* Separator */}
            <div className="hidden md:block w-px h-8 bg-border" />

              <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-xl border border-white/5 bg-white/5 text-[10px] font-black uppercase tracking-widest text-slate-400">
                <Activity className="w-3.5 h-3.5 text-emerald-400" />
                <span>Discussion: {messages.length} Message{messages.length > 1 ? "s" : ""}</span>
              </div>
            </div>
                <div className="flex items-center gap-4">
            {/* User Role Badge */}
            <div className={`flex items-center gap-2 px-3 py-1.5 rounded-xl border ${
              localStorage.getItem("pm_user") && (JSON.parse(localStorage.getItem("pm_user")!).roles?.some((r: string) => r.toUpperCase().includes("CEO")) || JSON.parse(localStorage.getItem("pm_user")!).role?.toUpperCase().includes("CEO"))
                ? "bg-primary/10 border-primary/20 text-primary"
                : "bg-emerald-500/10 border-emerald-500/20 text-emerald-400"
            }`}>
              <div className="w-1.5 h-1.5 rounded-full bg-emerald-500 shadow-[0_0_8px_rgba(16,185,129,0.6)] animate-pulse" />
              <span className="text-[10px] font-black text-muted-foreground uppercase tracking-widest">
                {localStorage.getItem("pm_user") && (JSON.parse(localStorage.getItem("pm_user")!).roles?.some((r: string) => r.toUpperCase().includes("CEO")) || JSON.parse(localStorage.getItem("pm_user")!).role?.toUpperCase().includes("CEO"))
                  ? "Vue CEO"
                  : "Vue Chef de Projet"
                }
              </span>
            </div>

            {/* Notifications Alert Bubble */}
            <div className="relative">
              <button
                onClick={() => setShowNotifications(!showNotifications)}
                className={`w-9 h-9 rounded-xl flex items-center justify-center border transition-all relative
                  ${showNotifications 
                    ? "bg-primary/20 border-primary/40 text-primary" 
                    : "bg-slate-800/20 border-slate-700/30 text-slate-400 hover:text-white hover:bg-slate-800/50"}`}
                title="Notifications & Alertes"
              >
                <Bell className={`w-4 h-4 ${displayedAlerts.length > 0 ? "animate-bounce" : ""}`} />
                {displayedAlerts.length > 0 && (
                  <span className="absolute -top-1 -right-1 w-4 h-4 rounded-full bg-red-500 text-[9px] font-black text-white flex items-center justify-center shadow-[0_0_8px_rgba(239,68,68,0.8)] animate-pulse">
                    {displayedAlerts.length}
                  </span>
                )}
              </button>

              {/* Notifications Dropdown Drawer */}
              {showNotifications && (
                <div className="absolute right-0 mt-2 w-80 bg-slate-900/95 dark:bg-slate-950/95 border border-white/10 rounded-2xl shadow-2xl backdrop-blur-2xl p-4 z-50 animate-fade-in flex flex-col gap-3">
                  <div className="flex items-center justify-between border-b border-white/5 pb-2">
                    <div className="flex items-center gap-2">
                      <Bell className="w-4 h-4 text-primary" />
                      <span className="text-xs font-black uppercase tracking-wider text-white">Alertes</span>
                    </div>
                    {displayedAlerts.length > 0 && (
                      <button
                        onClick={handleClearAllAlerts}
                        className="text-[9px] font-black uppercase tracking-widest text-slate-500 hover:text-red-400 transition-colors"
                      >
                        Tout effacer
                      </button>
                    )}
                  </div>

                  <div className="max-h-60 overflow-y-auto space-y-2.5 scrollbar-none pr-1">
                    {displayedAlerts.length === 0 ? (
                      <div className="text-center py-6 text-[10px] font-bold text-slate-500 uppercase tracking-wider">
                        Aucune nouvelle alerte
                      </div>
                    ) : (
                      displayedAlerts.map((alert, idx) => (
                        <div
                          key={alert.id || idx}
                          className={`p-3 rounded-xl border flex items-start gap-2.5 transition-all group relative overflow-hidden
                            ${alert.level === 'critique' ? 'bg-red-500/5 border-red-500/10 hover:border-red-500/25 text-red-400' : 'bg-amber-500/5 border-amber-500/10 hover:border-amber-500/25 text-amber-400'}`}
                        >
                          <div className={`p-1.5 rounded-lg shrink-0 ${alert.level === 'critique' ? 'bg-red-500/10' : 'bg-amber-500/10'}`}>
                            <AlertTriangle className="w-3.5 h-3.5" />
                          </div>
                          <div className="flex-1 min-w-0 pr-6">
                            <div className="flex flex-wrap items-center gap-1.5 mb-1">
                              <span className="text-[8px] font-black uppercase tracking-widest opacity-60">Alerte IA {alert.type}</span>
                              {alert.project_name && (
                                <span className="px-1.5 py-0.5 rounded text-[8px] font-black uppercase tracking-widest bg-slate-800 text-emerald-400 border border-emerald-500/10">
                                  {alert.project_name}
                                </span>
                              )}
                            </div>
                            <p className="text-[11px] font-bold leading-normal text-white break-words">{alert.message}</p>
                          </div>
                          
                          {/* Dismiss with a close button (X) */}
                          <button
                            onClick={() => handleDismissAlert(alert.id)}
                            className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 rounded-lg flex items-center justify-center bg-white/5 border border-white/10 text-slate-400 hover:text-white hover:bg-red-500/20 hover:border-red-500/30 transition-all opacity-0 group-hover:opacity-100"
                            title="Supprimer"
                          >
                            <X className="w-3 h-3" />
                          </button>
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {activeConvId && (
              <Button
                variant="ghost"
                size="icon"
                onClick={handleClearChat}
                className="w-9 h-9 rounded-xl text-slate-400 hover:text-red-400 hover:bg-red-400/10 transition-colors"
                title="Supprimer la conversation"
              >
                <Trash2 className="w-4 h-4" />
              </Button>
            )}
          </div>
        </header>

        <ScrollArea className="flex-1 p-0">
          <div className="max-w-5xl mx-auto py-6 space-y-4 px-4">
            {messages.length === 0 && !loading && (
              <div className="flex flex-col items-center justify-center h-[65vh] text-center space-y-6 animate-in fade-in zoom-in duration-700">
                <div className="relative">
                  <div className="absolute inset-0 bg-primary/20 blur-3xl rounded-full" />
                  <div className="relative w-24 h-24 bg-gradient-to-br from-primary to-indigo-600 rounded-[32px] flex items-center justify-center mb-4 border border-white/10 shadow-2xl rotate-6 animate-float">
                    <Bot className="w-12 h-12 text-white" />
                  </div>
                </div>
                <div className="space-y-2">
                  <h1 className="text-4xl font-black text-foreground tracking-tighter sm:text-5xl">Analyse Intelligente</h1>
                  <p className="text-foreground max-w-sm mx-auto leading-relaxed text-base font-bold">
                    Posez vos questions sur le projet <span className="text-primary font-black">{projectName}</span>. Je traite les données Redmine en temps réel.
                  </p>
                </div>
              </div>
            )}

            {messages.map((msg, i) => (
              <div key={i} className={`flex gap-3 animate-scale-in duration-500 ${msg.role === "assistant" ? "flex-row items-start" : "flex-row-reverse items-start"}`}>
                <div className={`w-10 h-10 rounded-xl flex items-center justify-center shrink-0 shadow-2xl transition-transform hover:scale-110 ${msg.role === "assistant"
                  ? "bg-gradient-to-br from-primary to-emerald-500 text-white glow-primary"
                  : "bg-slate-800 text-slate-300 border border-white/10"
                  }`}>
                  {msg.role === "assistant" ? <Bot className="w-5.5 h-5.5" /> : <UserIcon className="w-5.5 h-5.5" />}
                </div>

                <div className={`flex flex-col space-y-1 max-w-[75%] ${msg.role === "user" ? "items-end" : "items-start"}`}>
                  <div className="flex items-center gap-2 px-1">
                    <span className="font-black text-[9px] text-slate-500 uppercase tracking-[0.2em]">
                      {msg.role === "assistant" ? "Assistant" : "Utilisateur"}
                    </span>
                  </div>

                  <div className={`px-4 py-2.5 rounded-[20px] shadow-xl relative overflow-hidden transition-all hover:shadow-primary/20 ${msg.role === "assistant"
                    ? "bg-card backdrop-blur-xl border border-border text-foreground"
                    : "bg-primary/10 backdrop-blur-md border border-primary/30 text-foreground rounded-tr-none shadow-lg shadow-primary/5"
                    }`}>
                    <div className="text-sm leading-relaxed prose prose-slate dark:prose-invert prose-p:my-0 prose-pre:bg-slate-950/50 prose-pre:border prose-pre:border-border max-w-none pr-6 group relative">
                      <ReactMarkdown
                        remarkPlugins={[remarkGfm]}
                        components={{
                          table: ({ children }) => (
                            <div className="overflow-x-auto my-3 rounded-xl border border-white/10 shadow-lg">
                              <table className="w-full text-xs border-collapse">{children}</table>
                            </div>
                          ),
                          thead: ({ children }) => (
                            <thead className="bg-primary/20 text-primary">{children}</thead>
                          ),
                          tbody: ({ children }) => (
                            <tbody className="divide-y divide-white/5">{children}</tbody>
                          ),
                          tr: ({ children }) => (
                            <tr className="hover:bg-white/5 transition-colors">{children}</tr>
                          ),
                          th: ({ children }) => (
                            <th className="px-4 py-2.5 text-left font-black uppercase tracking-widest text-[10px] text-primary whitespace-nowrap">{children}</th>
                          ),
                          td: ({ children }) => (
                            <td className="px-4 py-2 text-slate-300 font-medium">{children}</td>
                          ),
                          strong: ({ children }) => (
                            <strong className="font-bold text-slate-200">{children}</strong>
                          ),
                          code: ({ children }) => (
                            <code className="bg-slate-800/80 text-emerald-400 px-1.5 py-0.5 rounded text-[11px] font-mono">{children}</code>
                          ),
                        }}
                      >{msg.content}</ReactMarkdown>

                      {msg.id && (
                        <button
                          onClick={() => handleDeleteMessage(msg.id)}
                          className="absolute top-0 -right-2 p-1 text-slate-500 hover:text-red-400 opacity-0 group-hover:opacity-100 transition-all"
                          title="Supprimer ce message"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      )}
                    </div>

                    {msg.display_type === "action_confirmation" && msg.data && (msg.data.action_type || msg.data.actions) && (
                      <div className="mt-5 space-y-4">
                        <div className="bg-slate-950/40 rounded-2xl p-5 border border-primary/20 shadow-inner">
                          <div className="flex items-center gap-2 mb-4">
                            <div className="w-2 h-2 bg-amber-500 rounded-full animate-pulse" />
                            <h4 className="text-sm font-bold text-amber-500 uppercase tracking-wider">
                              {msg.data.actions ? `${msg.data.actions.length} Actions Planifiées` : "Confirmation Requise"}
                            </h4>
                          </div>

                          <div className="space-y-6">
                            {(msg.data.actions || [{ action_type: msg.data.action_type, parameters: msg.data.parameters, description: msg.data.description || msg.data.summary }])
                              .map((rawAction: any) => {
                                const action = rawAction; // Mutate original reference to preserve changes for handleTaskExecution
                                if (action.parameters) {
                                  if (action.action_type === 'create_issue') {
                                    const defaultParams: any = {
                                      subject: '',
                                      description: '',
                                      tracker_id: null,
                                      status_id: null,
                                      priority_id: null,
                                      user_id: '',
                                      fixed_version: '',
                                      estimated_hours: '',
                                      start_date: (() => {
                                        const d = new Date();
                                        return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
                                      })(),
                                      due_date: ''
                                    };
                                    for (const [k, v] of Object.entries(defaultParams)) {
                                      if (action.parameters[k] === undefined || action.parameters[k] === null) {
                                        action.parameters[k] = v;
                                      }
                                    }
                                  } else if (action.action_type === 'update_issue') {
                                    const defaultParams: any = {
                                      issue_id: '',
                                      notes: '',
                                      status_id: null,
                                      priority_id: null,
                                      user_id: '',
                                      estimated_hours: '',
                                      done_ratio: null,
                                      start_date: '',
                                      due_date: ''
                                    };
                                    for (const [k, v] of Object.entries(defaultParams)) {
                                      if (action.parameters[k] === undefined || action.parameters[k] === null) {
                                        action.parameters[k] = v;
                                      }
                                    }
                                  }
                                }
                                return action;
                              })
                              .map((action: any, idx: number) => (
                              <div key={idx} className={`p-4 bg-white/5 rounded-xl border ${action.action_type.startsWith('delete') ? 'border-red-500/30 bg-red-500/5' : 'border-white/5'}`}>
                                <div className="flex items-center gap-2 mb-3">
                                  {action.action_type.startsWith('delete') && <XCircle className="w-3.5 h-3.5 text-red-500" />}
                                  <p className={`text-xs font-bold uppercase ${action.action_type.startsWith('delete') ? 'text-red-400' : 'text-primary'}`}>
                                    {action.description || action.action_type}
                                  </p>
                                </div>
                                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                                  {Object.entries(action.parameters || {}).map(([key, value]) => {
                                    const isMissing = value === undefined || value === null || value === "" || (Array.isArray(value) && value.length === 0);

                                     // ── RENDU SPÉCIAL POUR CREATE_VERSION ─────
                                     if (action.action_type === 'create_version') {
                                       if (key === 'name') {
                                         return (
                                           <div key={key} className="flex flex-col">
                                             <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                                               Nom du sprint / version
                                               <span className="px-1.5 py-0.5 rounded text-[8px] bg-red-500/20 text-red-400">Requis</span>
                                             </span>
                                             <input
                                               type="text"
                                               defaultValue={isMissing ? '' : String(value)}
                                               placeholder="Ex: Sprint 1"
                                               className={`bg-slate-900/50 border rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-primary/50 transition-colors ${isMissing ? 'border-red-500/30' : 'border-white/10'}`}
                                               onChange={(e) => { action.parameters[key] = e.target.value; }}
                                             />
                                           </div>
                                         )
                                       }

                                       if (key === 'description') {
                                         return (
                                           <div key={key} className="flex flex-col col-span-1 md:col-span-2">
                                             <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                                               Description
                                               <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Optionnel</span>
                                             </span>
                                             <textarea
                                               defaultValue={isMissing ? '' : String(value)}
                                               placeholder="Objectifs du sprint, périmètre..."
                                               className="bg-slate-900/50 border border-white/10 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-primary/50 min-h-[60px]"
                                               onChange={(e) => { action.parameters[key] = e.target.value; }}
                                             />
                                           </div>
                                         )
                                       }

                                       if (key === 'issue_ids') {
                                         return null;
                                       }

                                       if (['name', 'description', 'issue_ids'].includes(key)) return null;
                                     }

                                     // ── RENDU SPÉCIAL POUR DELETE_VERSION ─────
                                     if (action.action_type === 'delete_version') {
                                       if (key === 'name') {
                                         return (
                                           <div key={key} className="flex flex-col col-span-1 md:col-span-2 font-sans">
                                             <span className="text-[9px] text-red-400 uppercase tracking-wider mb-1 flex items-center gap-1.5 font-semibold">
                                               Nom du sprint / version à supprimer
                                               <span className="px-1.5 py-0.5 rounded text-[8px] bg-red-500/20 text-red-400">Requis</span>
                                             </span>
                                             <input
                                               type="text"
                                               defaultValue={isMissing ? '' : String(value)}
                                               placeholder="Ex: s.4"
                                               className="bg-slate-900/50 border border-red-500/30 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-red-500/50 transition-colors"
                                               onChange={(e) => { action.parameters[key] = e.target.value; }}
                                             />
                                           </div>
                                         )
                                       }
                                       if (['name', 'project_id'].includes(key)) return null;
                                     }

                                     // ── RENDU SPÉCIAL POUR UPDATE_VERSION ─────
                                     if (action.action_type === 'update_version') {
                                       if (key === 'name') {
                                         return (
                                           <div key={key} className="flex flex-col font-sans">
                                             <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1.5 font-semibold">
                                               Sprint à modifier
                                               <span className="px-1.5 py-0.5 rounded text-[8px] bg-red-500/20 text-red-400">Requis</span>
                                             </span>
                                             <input
                                               type="text"
                                               defaultValue={isMissing ? '' : String(value)}
                                               placeholder="Ex: s.4"
                                               className="bg-slate-900/50 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-primary/50 transition-colors"
                                               onChange={(e) => { action.parameters[key] = e.target.value; }}
                                             />
                                           </div>
                                         )
                                       }
                                       if (key === 'new_name') {
                                         return (
                                           <div key={key} className="flex flex-col font-sans">
                                             <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1.5 font-semibold">
                                               Nouveau nom du sprint
                                               <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Optionnel</span>
                                             </span>
                                             <input
                                               type="text"
                                               defaultValue={isMissing ? '' : String(value)}
                                               placeholder="Ex: s.5 (pour renommer)"
                                               className="bg-slate-900/50 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-primary/50 transition-colors"
                                               onChange={(e) => { action.parameters[key] = e.target.value; }}
                                             />
                                           </div>
                                         )
                                       }
                                       if (key === 'description') {
                                         return (
                                           <div key={key} className="flex flex-col col-span-1 md:col-span-2 font-sans">
                                             <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1.5 font-semibold">
                                               Nouvelle description
                                               <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Optionnel</span>
                                             </span>
                                             <textarea
                                               defaultValue={isMissing ? '' : String(value)}
                                               placeholder="Objectifs mis à jour..."
                                               className="bg-slate-900/50 border border-white/10 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-primary/50 min-h-[60px]"
                                               onChange={(e) => { action.parameters[key] = e.target.value; }}
                                             />
                                           </div>
                                         )
                                       }
                                        if (key === 'project_id') {
                                          return (
                                            <div key={key} className="flex flex-col col-span-1 md:col-span-2 font-sans mt-1">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1.5 font-semibold">
                                                Associer / Retirer des tâches du sprint
                                                <span className="px-1.5 py-0.5 rounded text-[8px] bg-emerald-500/20 text-emerald-400">Interactif</span>
                                              </span>
                                              <SprintTaskSelector
                                                projectId={String(value || '')}
                                                sprintName={String(action.parameters.name || '')}
                                                onChange={(ids) => {
                                                  action.parameters.issue_ids = ids;
                                                }}
                                              />
                                            </div>
                                          )
                                        }
                                        if (['name', 'new_name', 'description', 'project_id', 'issue_ids'].includes(key)) return null;
                                      }

                                    // ── RENDU SPÉCIAL POUR CREATE_USER (DOIT ÊTRE EN PREMIER) ─────
                                    if (action.action_type === 'create_user') {
                                      const USER_CREATE_FIELDS: Record<string, { label: string; type: string; placeholder: string }> = {
                                        firstname: { label: 'Prénom', type: 'text', placeholder: 'Ex: Ismail' },
                                        lastname: { label: 'Nom', type: 'text', placeholder: 'Ex: Benhaddou' },
                                        login: { label: 'Identifiant', type: 'text', placeholder: 'Ex: ismail.benhaddou' },
                                        mail: { label: 'Email', type: 'email', placeholder: 'Ex: ismail@pfe.local' },
                                        password: { label: 'Mot de passe', type: 'password', placeholder: 'Min. 8 caractères' },
                                      };
                                      if (key in USER_CREATE_FIELDS) {
                                        const fieldDef = USER_CREATE_FIELDS[key];
                                        return (
                                          <div key={key} className="flex flex-col">
                                            <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-1.5">
                                              {fieldDef.label}
                                              <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Requis</span>
                                            </span>
                                            <input
                                              type={fieldDef.type}
                                              defaultValue={isMissing ? '' : String(value)}
                                              placeholder={fieldDef.placeholder}
                                              className={`bg-slate-900/50 border rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-primary/50 transition-colors ${isMissing ? 'border-amber-500/30' : 'border-white/10'}`}
                                              onChange={(e) => { action.parameters[key] = e.target.value; }}
                                            />
                                          </div>
                                        )
                                      }
                                      return null; // masquer tous les autres champs pour create_user
                                    }

                                    // Masquer le mot de passe pour toutes les autres actions
                                    if (key === 'password') return null;

                                    // Masquer les champs techniques ou redondants
                                    const HIDDEN_FIELDS = ['firstname', 'lastname', 'mail', 'login', 'password'];
                                    if (HIDDEN_FIELDS.includes(key)) return null;

                                    if (key === 'project_id' && !isMissing) {
                                      // Masquer le projet pour les actions qui ont déjà leur contexte
                                      if (['update_issue', 'create_project'].includes(action.action_type)) return null;
                                      return (
                                        <div key={key} className="flex flex-col">
                                          <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Projet</span>
                                          <input type="text" readOnly defaultValue={String(value)} className="bg-slate-900/30 border border-white/5 rounded-lg px-3 py-1.5 text-xs text-slate-400 focus:outline-none" />
                                        </div>
                                      )
                                    }

                                    if (key === 'copy_roles_from' && !isMissing) {
                                      return (
                                        <div key={key} className="flex flex-col col-span-1 md:col-span-2">
                                          <span className="text-[9px] text-primary uppercase tracking-wider mb-1 flex items-center gap-1.5">
                                            <Bot className="w-3 h-3" /> Héritage des rôles
                                          </span>
                                          <div className="bg-primary/5 border border-primary/20 rounded-lg px-3 py-1.5 text-xs text-primary font-bold">
                                            Prendre la place de : {String(value)}
                                          </div>
                                        </div>
                                      )
                                    }

                                    // ── SÉLECTEUR DE RÔLE pour add_project_member ─────────────────
                                    if (action.action_type === 'add_project_member') {
                                      if (key === 'role' && !isMissing) {
                                        // Rôle fourni par le LLM → lecture seule
                                        return (
                                          <div key={key} className="flex flex-col col-span-1 md:col-span-2">
                                            <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Rôle attribué</span>
                                            <div className="bg-primary/10 border border-primary/30 rounded-lg px-3 py-2 text-xs text-primary font-bold">{String(value)}</div>
                                          </div>
                                        )
                                      }
                                      if (key === 'role_ids' && !isMissing && !action.parameters.role) {
                                        const ROLE_NAMES: Record<number, string> = { 3: 'Chef de projet', 4: 'Développeur', 5: 'Rapporteur', 6: 'CEO' };
                                        const roleArr = Array.isArray(value) ? value : [value];
                                        const roleLabel = roleArr.map((id: number) => ROLE_NAMES[id] || `Rôle ${id}`).join(', ');
                                        return (
                                          <div key={key} className="flex flex-col col-span-1 md:col-span-2">
                                            <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Rôle attribué</span>
                                            <div className="bg-primary/10 border border-primary/30 rounded-lg px-3 py-2 text-xs text-primary font-bold">{roleLabel}</div>
                                          </div>
                                        )
                                      }
                                      // Rôle manquant → sélecteur radio
                                      if ((key === 'role' || key === 'role_ids') && isMissing && !action.parameters.role && !(action.parameters.role_ids?.length)) {
                                        if (key !== 'role') return null;
                                        return (
                                          <div key="role-selector" className="flex flex-col col-span-1 md:col-span-2 mt-1">
                                            <span className="text-[9px] text-amber-400 uppercase tracking-wider mb-2 flex items-center gap-1.5">
                                              Rôle <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Requis</span>
                                            </span>
                                            <div className="grid grid-cols-2 gap-2">
                                              {[
                                                { id: 6, label: 'CEO' },
                                                { id: 3, label: 'Chef de projet' },
                                                { id: 4, label: 'Développeur' },
                                                { id: 5, label: 'Rapporteur' },
                                              ].map((opt, optIdx) => (
                                                <label key={optIdx} className="flex items-center justify-center gap-2 cursor-pointer text-xs font-bold text-white bg-white/5 hover:bg-white/10 border border-white/10 hover:border-white/20 rounded-xl px-3 py-2.5 transition-all has-[:checked]:bg-gradient-to-r has-[:checked]:border-transparent">
                                                  <input type="radio" name={`role_${idx}`} className="sr-only"
                                                    onChange={() => { action.parameters.role = opt.label; action.parameters.role_ids = [opt.id]; }}
                                                  />
                                                  {opt.label}
                                                </label>
                                              ))}
                                            </div>
                                          </div>
                                        )
                                      }
                                      // Pour add_project_member, masquer les champs role/role_ids après gestion ci-dessus
                                      if (key === 'role' || key === 'role_ids') return null;
                                    }

                                    // ── CHAMPS role/role_ids pour les AUTRES actions ───────────────
                                    if (key === 'role' && !isMissing) {
                                      return (
                                        <div key={key} className="flex flex-col">
                                          <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Rôle</span>
                                          <input type="text" readOnly defaultValue={String(value)} className="bg-slate-900/30 border border-white/5 rounded-lg px-3 py-1.5 text-xs text-white font-medium focus:outline-none" />
                                        </div>
                                      )
                                    }

                                    if (key === 'role_ids' && !isMissing && !action.parameters.role) {
                                      const ROLE_NAMES: Record<number, string> = { 3: 'Chef de projet', 4: 'Développeur', 5: 'Rapporteur', 6: 'CEO' };
                                      const roleArr = Array.isArray(value) ? value : [value];
                                      const roleLabel = roleArr.map((id: number) => ROLE_NAMES[id] || `Rôle ${id}`).join(', ');
                                      return (
                                        <div key={key} className="flex flex-col">
                                          <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Rôle</span>
                                          <input type="text" readOnly defaultValue={roleLabel} className="bg-slate-900/30 border border-white/5 rounded-lg px-3 py-1.5 text-xs text-white font-medium focus:outline-none" />
                                        </div>
                                      )
                                    }

                                    if ((key === 'user_id' || key === 'utilisateur') && !isMissing) {
                                      return (
                                        <div key={key} className="flex flex-col">
                                          <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Assigné à</span>
                                          <input type="text" readOnly defaultValue={String(value)} className="bg-slate-900/30 border border-white/5 rounded-lg px-3 py-1.5 text-xs text-slate-400 focus:outline-none" />
                                        </div>
                                      )
                                    }

                                    if (key === 'issue_id' && !isMissing) {
                                      return (
                                        <div key={key} className="flex flex-col">
                                          <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Ticket #</span>
                                          <input type="text" readOnly defaultValue={String(value)} className="bg-slate-900/30 border border-white/5 rounded-lg px-3 py-1.5 text-xs text-slate-400 focus:outline-none" />
                                        </div>
                                      )
                                    }

                                    if (key === 'identifier' && !isMissing) {
                                      return (
                                        <div key={key} className="flex flex-col">
                                          <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Identifiant</span>
                                          <input type="text" readOnly defaultValue={String(value)} className="bg-slate-900/30 border border-white/5 rounded-lg px-3 py-1.5 text-xs text-slate-400 focus:outline-none" />
                                        </div>
                                      )
                                    }

                                    // ── TRACKER_ID → nom lisible ───────────────────────────────────
                                    if (key === 'tracker_id' && !isMissing) {
                                      const TRACKER_NAMES: Record<number, { label: string; color: string }> = {
                                        1: { label: 'Anomalie', color: 'bg-red-500/20 text-red-400 border-red-500/30' },
                                        2: { label: 'Évolution', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
                                        3: { label: 'Assistance', color: 'bg-teal-500/20 text-teal-400 border-teal-500/30' },
                                      };
                                      const tracker = TRACKER_NAMES[Number(value)] || { label: String(value), color: 'bg-slate-500/20 text-slate-400 border-slate-500/30' };
                                      return (
                                        <div key={key} className="flex flex-col">
                                          <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Type</span>
                                          <div className={`border rounded-lg px-3 py-1.5 text-xs font-bold ${tracker.color}`}>{tracker.label}</div>
                                        </div>
                                      )
                                    }

                                    // ── STATUS_ID / ÉTAT_ID → nom lisible ─────────────────────────
                                    if ((key === 'status_id' || key === 'état_id') && !isMissing) {
                                      const STATUS_NAMES: Record<number, { label: string; color: string }> = {
                                        1: { label: 'Nouveau', color: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' },
                                        2: { label: 'En cours', color: 'bg-blue-500/20 text-blue-400 border-blue-500/30' },
                                        3: { label: 'Résolu', color: 'bg-violet-500/20 text-violet-400 border-violet-500/30' },
                                        4: { label: 'Commentaire', color: 'bg-amber-500/20 text-amber-400 border-amber-500/30' },
                                        5: { label: 'Fermé', color: 'bg-slate-500/20 text-slate-400 border-slate-500/30' },
                                        6: { label: 'Rejeté', color: 'bg-red-500/20 text-red-400 border-red-500/30' },
                                      };
                                      const status = STATUS_NAMES[Number(value)] || { label: String(value), color: 'bg-slate-500/20 text-slate-400 border-slate-500/30' };
                                      return (
                                        <div key={key} className="flex flex-col">
                                          <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Statut</span>
                                          <div className={`border rounded-lg px-3 py-1.5 text-xs font-bold ${status.color}`}>{status.label}</div>
                                        </div>
                                      )
                                    }

                                    if (action.action_type === 'update_issue') {
                                      if (key === 'issue_id') {
                                        if (isMissing) {
                                          return (
                                            <div key={key} className="flex flex-col">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">ID du ticket <span className="px-1.5 py-0.5 rounded text-[8px] bg-red-500/20 text-red-400">Requis</span></span>
                                              <input type="number" placeholder="Ex: 42" className="bg-slate-900/50 border border-red-500/30 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-red-500" onChange={(e) => { action.parameters[key] = e.target.value; }} />
                                            </div>
                                          )
                                        } else {
                                          return (
                                            <div key={key} className="flex flex-col">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Ticket #</span>
                                              <input type="text" readOnly defaultValue={String(value)} className="bg-slate-900/30 border border-white/5 rounded-lg px-3 py-1.5 text-xs text-slate-400 focus:outline-none" />
                                            </div>
                                          )
                                        }
                                      }



                                      if (key === 'notes') {
                                        if (isMissing) {
                                          return (
                                            <div key={key} className="flex flex-col col-span-1 md:col-span-2 mt-2">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">Commentaire <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Optionnel</span></span>
                                              <textarea placeholder="Ajouter une note au ticket..." className="bg-slate-900/50 border border-white/10 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-primary/50 min-h-[60px]" onChange={(e) => { action.parameters[key] = e.target.value; }} />
                                            </div>
                                          )
                                        } else {
                                          return (
                                            <div key={key} className="flex flex-col col-span-1 md:col-span-2 mt-2">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Commentaire ajouté</span>
                                              <textarea readOnly defaultValue={String(value)} className="bg-slate-900/30 border border-white/5 rounded-lg px-3 py-2 text-xs text-slate-400 focus:outline-none min-h-[60px]" />
                                            </div>
                                          )
                                        }
                                      }
                                    }

                                    if (action.action_type === 'create_issue' || action.action_type === 'update_issue') {
                                      if (key === 'status_id') {
                                        if (isMissing) {
                                          return (
                                            <div key={key} className="flex flex-col col-span-1 md:col-span-2 mt-2">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">
                                                {action.action_type === 'create_issue' ? 'Statut de départ' : 'Nouveau Statut'}{' '}
                                                <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Optionnel</span>
                                              </span>
                                              <div className="flex flex-wrap gap-4">
                                                {[{ id: 1, label: 'Nouveau' }, { id: 2, label: 'En cours' }, { id: 3, label: 'Résolu' }, { id: 4, label: 'Commentaire' }, { id: 5, label: 'Fermé' }, { id: 6, label: 'Rejeté' }].map(opt => (
                                                  <label key={opt.id} className="flex items-center gap-2 cursor-pointer text-xs text-slate-200">
                                                    <input type="radio" name={`status_${idx}`} onChange={() => { action.parameters[key] = opt.id; }} className="accent-primary" /> {opt.label}
                                                  </label>
                                                ))}
                                              </div>
                                            </div>
                                          )
                                        } else {
                                          const label = value === 1 ? 'Nouveau' : value === 2 ? 'En cours' : value === 3 ? 'Résolu' : value === 4 ? 'Commentaire' : value === 5 ? 'Fermé' : value === 6 ? 'Rejeté' : value;
                                          return (
                                            <div key={key} className="flex flex-col">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">
                                                {action.action_type === 'create_issue' ? 'Statut de départ' : 'Nouveau Statut'}
                                              </span>
                                              <input type="text" readOnly defaultValue={String(label)} className="bg-slate-900/30 border border-white/5 rounded-lg px-3 py-1.5 text-xs text-slate-400 focus:outline-none" />
                                            </div>
                                          )
                                        }
                                      }

                                      if (key === 'tracker_id') {
                                        if (isMissing) {
                                          return (
                                            <div key={key} className="flex flex-col col-span-1 md:col-span-2 mt-2">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">Type de tâche (Tracker) <span className={`px-1.5 py-0.5 rounded text-[8px] ${action.action_type === 'create_issue' ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400'}`}>{action.action_type === 'create_issue' ? 'À compléter' : 'Optionnel'}</span></span>
                                              <div className="flex gap-4">
                                                {[{ id: 1, label: 'Anomalie' }, { id: 2, label: 'Évolution' }, { id: 3, label: 'Assistance' }].map(opt => (
                                                  <label key={opt.id} className="flex items-center gap-2 cursor-pointer text-xs text-slate-200">
                                                    <input type="radio" name={`tracker_${idx}`} onChange={() => { action.parameters[key] = opt.id; }} className="accent-primary" /> {opt.label}
                                                  </label>
                                                ))}
                                              </div>
                                            </div>
                                          )
                                        } else {
                                          const label = value === 1 ? 'Anomalie' : value === 2 ? 'Évolution' : value === 3 ? 'Assistance' : value;
                                          return (
                                            <div key={key} className="flex flex-col">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Tracker</span>
                                              <input type="text" readOnly defaultValue={String(label)} className="bg-slate-900/30 border border-white/5 rounded-lg px-3 py-1.5 text-xs text-slate-400 focus:outline-none" />
                                            </div>
                                          )
                                        }
                                      }

                                      if (key === 'priority_id') {
                                        if (isMissing) {
                                          return (
                                            <div key={key} className="flex flex-col col-span-1 md:col-span-2 mt-2">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-2 flex items-center gap-2">Priorité <span className={`px-1.5 py-0.5 rounded text-[8px] ${action.action_type === 'create_issue' ? 'bg-red-500/20 text-red-400' : 'bg-amber-500/20 text-amber-400'}`}>{action.action_type === 'create_issue' ? 'À compléter' : 'Optionnel'}</span></span>
                                              <div className="flex flex-wrap gap-4">
                                                {[{ id: 1, label: 'Bas' }, { id: 2, label: 'Normal' }, { id: 3, label: 'Haut' }, { id: 4, label: 'Urgent' }, { id: 5, label: 'Immédiat' }].map(opt => (
                                                  <label key={opt.id} className="flex items-center gap-2 cursor-pointer text-xs text-slate-200">
                                                    <input type="radio" name={`priority_${idx}`} onChange={() => { action.parameters[key] = opt.id; }} className="accent-primary" /> {opt.label}
                                                  </label>
                                                ))}
                                              </div>
                                            </div>
                                          )
                                        } else {
                                          const label = value === 1 ? 'Bas' : value === 2 ? 'Normal' : value === 3 ? 'Haut' : value === 4 ? 'Urgent' : value === 5 ? 'Immédiat' : value;
                                          return (
                                            <div key={key} className="flex flex-col">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">Priorité</span>
                                              <input type="text" readOnly defaultValue={String(label)} className="bg-slate-900/30 border border-white/5 rounded-lg px-3 py-1.5 text-xs text-slate-400 focus:outline-none" />
                                            </div>
                                          )
                                        }
                                      }

                                      if (key === 'description') {
                                        if (isMissing) {
                                          return (
                                            <div key={key} className="flex flex-col col-span-1 md:col-span-2 mt-2">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">Description <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Optionnel</span></span>
                                              <textarea placeholder="Ajouter une description..." className="bg-slate-900/50 border border-white/10 rounded-lg px-3 py-2 text-xs text-white focus:outline-none focus:border-primary/50 min-h-[80px]" onChange={(e) => { action.parameters[key] = e.target.value; }} />
                                            </div>
                                          )
                                        }
                                      }

                                      if ((key === 'user_id' || key === 'utilisateur') && isMissing) {
                                        // Éviter d'afficher deux fois le champ si user_id et utilisateur sont tous deux vides
                                        if (key === 'utilisateur') return null;
                                        const otherValue = action.parameters[key === 'user_id' ? 'utilisateur' : 'user_id'];
                                        if (otherValue && otherValue !== "") return null;

                                        if (action.action_type === 'create_issue') {
                                          return (
                                            <div key={key} className="flex flex-col">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">Assigné à <span className="px-1.5 py-0.5 rounded text-[8px] bg-red-500/20 text-red-400">À compléter</span></span>
                                              <input type="text" placeholder="Nom de l'utilisateur" className="bg-slate-900/50 border border-red-500/30 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-red-500" onChange={(e) => { action.parameters[key] = e.target.value; }} />
                                            </div>
                                          )
                                        } else if (action.action_type === 'update_issue') {
                                          return (
                                            <div key={key} className="flex flex-col">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">Nouvel Assigné <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Optionnel</span></span>
                                              <input type="text" placeholder="Changer l'assignation..." className="bg-slate-900/50 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-primary/50" onChange={(e) => { action.parameters[key] = e.target.value; }} />
                                            </div>
                                          )
                                        }
                                      }

                                      if (key === 'subject' && isMissing) {
                                        if (action.action_type === 'create_issue') {
                                          return (
                                            <div key={key} className="flex flex-col col-span-1 md:col-span-2">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">Sujet <span className="px-1.5 py-0.5 rounded text-[8px] bg-red-500/20 text-red-400">À compléter</span></span>
                                              <input type="text" placeholder="Titre de la tâche" className="bg-slate-900/50 border border-red-500/30 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-red-500" onChange={(e) => { action.parameters[key] = e.target.value; }} />
                                            </div>
                                          )
                                        } else if (action.action_type === 'update_issue') {
                                          return null; // On cache le champ Sujet s'il est vide lors d'une modification pour alléger l'interface
                                        }
                                      }

                                      if (key === 'estimated_hours') {
                                        return (
                                          <div key={key} className="flex flex-col">
                                            <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">Temps estimé (h) <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Optionnel</span></span>
                                            <input type="number" step="0.5" min="0" placeholder="Ex: 2.5" defaultValue={isMissing ? '' : String(value)} className="bg-slate-900/50 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-primary/50" onChange={(e) => { action.parameters[key] = e.target.value; }} />
                                          </div>
                                        )
                                      }

                                      if (key === 'done_ratio') {
                                        if (isMissing) {
                                          return (
                                            <div key={key} className="flex flex-col">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">% Réalisé <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Optionnel</span></span>
                                              <div className="flex items-center gap-3 mt-1">
                                                <input type="range" min="0" max="100" step="10" defaultValue="0" className="flex-1 accent-primary" onChange={(e) => { action.parameters[key] = parseInt(e.target.value); e.target.nextElementSibling!.textContent = `${e.target.value}%`; }} />
                                                <span className="text-xs text-slate-400 w-8 text-right">0%</span>
                                              </div>
                                            </div>
                                          )
                                        } else {
                                          return (
                                            <div key={key} className="flex flex-col">
                                              <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">% Réalisé</span>
                                              <div className="flex items-center gap-3">
                                                <div className="flex-1 h-2 bg-slate-900/50 rounded-full overflow-hidden">
                                                  <div className="h-full bg-primary" style={{ width: `${value}%` }}></div>
                                                </div>
                                                <span className="text-xs text-slate-300 font-bold">{String(value)}%</span>
                                              </div>
                                            </div>
                                          )
                                        }
                                      }

                                      if (key === 'fixed_version') {
                                        return (
                                          <div key={key} className="flex flex-col">
                                            <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">Sprint / Version <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Optionnel</span></span>
                                            <input type="text" placeholder="Ex: s.4" defaultValue={isMissing ? '' : String(value)} className="bg-slate-900/50 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-primary/50" onChange={(e) => { action.parameters[key] = e.target.value; }} />
                                          </div>
                                        )
                                      }

                                      if (key === 'start_date') {
                                        return (
                                          <div key={key} className="flex flex-col">
                                            <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">Début <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Optionnel</span></span>
                                            <input type="date" defaultValue={isMissing ? '' : String(value)} className="bg-slate-900/50 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-primary/50 w-full" onChange={(e) => { action.parameters[key] = e.target.value; }} />
                                          </div>
                                        )
                                      }

                                      if (key === 'due_date') {
                                        return (
                                          <div key={key} className="flex flex-col">
                                            <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1 flex items-center gap-2">Échéance <span className="px-1.5 py-0.5 rounded text-[8px] bg-amber-500/20 text-amber-400">Optionnel</span></span>
                                            <input type="date" defaultValue={isMissing ? '' : String(value)} className="bg-slate-900/50 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-primary/50 w-full" onChange={(e) => { action.parameters[key] = e.target.value; }} />
                                          </div>
                                        )
                                      }
                                    }

                                    if (isMissing || ['name', 'description', 'issue_ids'].includes(key)) return null;

                                    return (
                                      <div key={key} className="flex flex-col">
                                        <span className="text-[9px] text-slate-500 uppercase tracking-wider mb-1">{key}</span>
                                        <input
                                          type="text"
                                          defaultValue={typeof value === 'object' ? JSON.stringify(value) : String(value)}
                                          className="bg-slate-900/50 border border-white/10 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:border-primary/50"
                                          onChange={(e) => { action.parameters[key] = e.target.value; }}
                                        />
                                      </div>
                                    )
                                  })}
                                </div>
                              </div>
                            ))}
                          </div>

                          <div className="flex gap-3 mt-6">
                            <Button
                              variant="outline"
                              className="flex-1 bg-transparent border-red-500/50 text-red-400 hover:bg-red-500/10 h-11 rounded-xl"
                              onClick={() => handleTaskExecution(msg.data.actions || [msg.data], i, false)}
                            >
                              <XCircle className="w-4 h-4 mr-2" /> Annuler
                            </Button>
                            <Button
                              className="flex-1 bg-gradient-to-r from-emerald-500 to-emerald-600 hover:from-emerald-400 hover:to-emerald-500 border-none h-11 rounded-xl"
                              onClick={() => handleTaskExecution(msg.data.actions || [msg.data], i, true)}
                            >
                              <CheckCircle2 className="w-4 h-4 mr-2" /> Valider
                            </Button>
                          </div>
                        </div>
                      </div>
                    )}

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

                    {msg.display_type === "issues_table" && msg.data && msg.data.issues && (
                      <div className="mt-5 overflow-hidden bg-card rounded-2xl border border-border shadow-2xl">
                        <div className="p-4 bg-red-500/10 border-b border-white/5 flex items-center gap-2">
                          <AlertTriangle className="w-4 h-4 text-red-500" />
                          <h4 className="text-xs font-black uppercase tracking-widest text-red-400">Tâches en Retard</h4>
                        </div>
                        <div className="overflow-x-auto">
                          <table className="w-full text-left text-[11px]">
                            <thead>
                              <tr className="border-b border-white/5 bg-white/5">
                                <th className="px-4 py-3 font-black uppercase tracking-tighter text-slate-500">ID</th>
                                <th className="px-4 py-3 font-black uppercase tracking-tighter text-slate-500">Sujet</th>
                                <th className="px-4 py-3 font-black uppercase tracking-tighter text-slate-500">Échéance</th>
                                <th className="px-4 py-3 font-black uppercase tracking-tighter text-slate-500">Assigné</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                              {msg.data.issues.map((issue: any) => (
                                <tr key={issue.id} className="hover:bg-white/5 transition-colors group">
                                  <td className="px-4 py-3 font-mono text-primary">#{issue.id}</td>
                                  <td className="px-4 py-3 font-bold text-slate-200">{issue.subject}</td>
                                  <td className="px-4 py-3">
                                    <div className="flex items-center gap-1.5 text-red-400 font-bold">
                                      <Clock className="w-3 h-3" />
                                      {issue.due_date || "N/A"}
                                    </div>
                                  </td>
                                  <td className="px-4 py-3 text-slate-400 group-hover:text-slate-200 transition-colors">{issue.assigned_to?.name || "Non assigné"}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {msg.display_type === "risk_table" && msg.data && msg.data.issues && (
                      <div className="mt-5 overflow-hidden bg-card rounded-2xl border border-border shadow-2xl">
                        <div className="p-4 bg-amber-500/10 border-b border-white/5 flex items-center gap-2">
                          <Shield className="w-4 h-4 text-amber-500" />
                          <h4 className="text-xs font-black uppercase tracking-widest text-amber-400">Analyse des Risques</h4>
                        </div>
                        <div className="overflow-x-auto">
                          <table className="w-full text-left text-[11px]">
                            <thead>
                              <tr className="border-b border-white/5 bg-white/5">
                                <th className="px-4 py-3 font-black uppercase tracking-tighter text-slate-500">Tâche</th>
                                <th className="px-4 py-3 font-black uppercase tracking-tighter text-slate-500">Priorité</th>
                                <th className="px-4 py-3 font-black uppercase tracking-tighter text-slate-500">Statut</th>
                                <th className="px-4 py-3 font-black uppercase tracking-tighter text-slate-500">Progrès</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                              {msg.data.issues.map((issue: any) => (
                                <tr key={issue.id} className="hover:bg-white/5 transition-colors">
                                  <td className="px-4 py-3">
                                    <div className="font-bold text-slate-200">{issue.subject}</div>
                                    <div className="text-[9px] text-slate-500 font-mono mt-0.5">#{issue.id}</div>
                                  </td>
                                  <td className="px-4 py-3">
                                    <span className={`px-2 py-0.5 rounded-full font-black uppercase tracking-tighter text-[9px] ${issue.priority?.name?.toLowerCase().includes('urgent') ? 'bg-red-500/20 text-red-400' :
                                      issue.priority?.name?.toLowerCase().includes('haut') ? 'bg-amber-500/20 text-amber-400' :
                                        'bg-slate-500/20 text-slate-400'
                                      }`}>
                                      {issue.priority?.name}
                                    </span>
                                  </td>
                                  <td className="px-4 py-3 text-slate-400">{issue.status?.name}</td>
                                  <td className="px-4 py-3">
                                    <div className="flex items-center gap-2">
                                      <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                                        <div className={`h-full ${issue.done_ratio > 70 ? 'bg-emerald-500' : issue.done_ratio > 30 ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${issue.done_ratio}%` }}></div>
                                      </div>
                                      <span className="font-mono text-[10px] text-slate-400">{issue.done_ratio}%</span>
                                    </div>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {msg.display_type === "projects_table" && msg.data && msg.data.projects && (
                      <div className="mt-5 overflow-hidden bg-card rounded-2xl border border-border shadow-2xl">
                        <div className="p-4 bg-primary/10 border-b border-white/5 flex items-center gap-2">
                          <BarChart3 className="w-4 h-4 text-primary" />
                          <h4 className="text-xs font-black uppercase tracking-widest text-white">État Global des Projets</h4>
                        </div>
                        <div className="overflow-x-auto">
                          <table className="w-full text-left text-[11px]">
                            <thead>
                              <tr className="border-b border-white/5 bg-white/5">
                                <th className="px-4 py-3 font-black uppercase tracking-tighter text-slate-500">Projet</th>
                                <th className="px-4 py-3 font-black uppercase tracking-tighter text-slate-500 text-center">Avancement</th>
                                <th className="px-4 py-3 font-black uppercase tracking-tighter text-slate-500 text-center">Retards</th>
                                <th className="px-4 py-3 font-black uppercase tracking-tighter text-slate-500 text-center">Critiques</th>
                              </tr>
                            </thead>
                            <tbody className="divide-y divide-white/5">
                              {msg.data.projects.map((proj: any) => (
                                <tr key={proj.identifier} className="hover:bg-white/5 transition-colors group">
                                  <td className="px-4 py-3">
                                    <div className="font-bold text-slate-200">{proj.name}</div>
                                    <div className="text-[9px] text-slate-500 font-mono mt-0.5">{proj.identifier}</div>
                                  </td>
                                  <td className="px-4 py-3 w-40">
                                    <div className="flex items-center gap-2">
                                      <div className="flex-1 h-1.5 bg-white/5 rounded-full overflow-hidden">
                                        <div className="h-full bg-primary" style={{ width: `${proj.progress}%` }}></div>
                                      </div>
                                      <span className="font-mono text-[10px] text-slate-400">{Math.round(proj.progress)}%</span>
                                    </div>
                                  </td>
                                  <td className="px-4 py-3 text-center">
                                    <span className={`px-2 py-1 rounded-lg font-black ${proj.overdue_issues > 0 ? 'bg-red-500/20 text-red-400' : 'bg-emerald-500/20 text-emerald-400'}`}>
                                      {proj.overdue_issues}
                                    </span>
                                  </td>
                                  <td className="px-4 py-3 text-center">
                                    <span className={`px-2 py-1 rounded-lg font-black ${proj.critical_issues > 0 ? 'bg-rose-600/30 text-rose-500 animate-pulse' : 'bg-slate-500/10 text-slate-500'}`}>
                                      {proj.critical_issues}
                                    </span>
                                  </td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                      </div>
                    )}

                    {msg.display_type === "metrics_card" && msg.data && (
                      <div className="mt-5 grid grid-cols-1 md:grid-cols-2 gap-4">
                        {/* Progress Card */}
                        <div className="bg-gradient-to-br from-indigo-600/20 to-primary/20 backdrop-blur-xl border border-white/10 rounded-[32px] p-6 shadow-2xl relative overflow-hidden group">
                          <div className="absolute top-0 right-0 p-4 opacity-10 group-hover:opacity-20 transition-opacity">
                            <Trophy className="w-20 h-20 text-white" />
                          </div>
                          <div className="relative">
                            <div className="flex items-center gap-3 mb-4">
                              <div className="w-10 h-10 bg-primary/20 rounded-xl flex items-center justify-center">
                                <Target className="w-5 h-5 text-primary" />
                              </div>
                              <h4 className="text-sm font-black uppercase tracking-widest text-white">Avancement Global</h4>
                            </div>
                            <div className="flex items-end gap-2 mb-2">
                              <span className="text-4xl font-black text-white">{Math.round(msg.data.avg_progress || 0)}%</span>
                              <span className="text-xs text-slate-400 mb-1.5 font-bold uppercase tracking-widest">Terminé</span>
                            </div>
                            <div className="h-3 bg-white/5 rounded-full overflow-hidden p-0.5 border border-white/5">
                              <div className="h-full bg-primary rounded-full shadow-[0_0_15px_rgba(169,14,34,0.3)] transition-all duration-1000" style={{ width: `${msg.data.avg_progress || 0}%` }} />
                            </div>
                          </div>
                        </div>

                        {/* Stats Grid */}
                        <div className="grid grid-cols-2 gap-4">
                          <div className="bg-card backdrop-blur-xl border border-border rounded-3xl p-5 flex flex-col justify-between hover:bg-primary/5 transition-all">
                            <div className="flex items-center justify-between">
                              <div className="w-8 h-8 bg-red-500/10 rounded-lg flex items-center justify-center">
                                <Clock className="w-4 h-4 text-red-500" />
                              </div>
                              <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Retards</span>
                            </div>
                            <div className="mt-4">
                              <div className="text-2xl font-black text-white">{msg.data.overdue_issues || 0}</div>
                              <div className="text-[10px] text-red-400 font-bold uppercase mt-1">Tâches échues</div>
                            </div>
                          </div>

                          <div className="bg-card backdrop-blur-xl border border-border rounded-3xl p-5 flex flex-col justify-between hover:bg-primary/5 transition-all">
                            <div className="flex items-center justify-between">
                              <div className="w-8 h-8 bg-amber-500/10 rounded-lg flex items-center justify-center">
                                <Zap className="w-4 h-4 text-amber-500" />
                              </div>
                              <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Critique</span>
                            </div>
                            <div className="mt-4">
                              <div className="text-2xl font-black text-white">{msg.data.critical_issues || 0}</div>
                              <div className="text-[10px] text-amber-400 font-bold uppercase mt-1">Priorité Haute</div>
                            </div>
                          </div>

                          <div className="bg-card backdrop-blur-xl border border-border rounded-3xl p-5 flex flex-col justify-between hover:bg-primary/5 transition-all">
                            <div className="flex items-center justify-between">
                              <div className="w-8 h-8 bg-emerald-500/10 rounded-lg flex items-center justify-center">
                                <CheckCircle2 className="w-4 h-4 text-emerald-500" />
                              </div>
                              <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Terminé</span>
                            </div>
                            <div className="mt-4">
                              <div className="text-2xl font-black text-foreground">{msg.data.done_issues || 0}</div>
                              <div className="text-[10px] text-emerald-400 font-bold uppercase mt-1">Total clos</div>
                            </div>
                          </div>

                          <div className="bg-card backdrop-blur-xl border border-border rounded-3xl p-5 flex flex-col justify-between hover:bg-primary/5 transition-all">
                            <div className="flex items-center justify-between">
                              <div className="w-8 h-8 bg-primary/10 rounded-lg flex items-center justify-center">
                                <BarChart3 className="w-4 h-4 text-primary" />
                              </div>
                              <span className="text-[10px] font-black text-slate-500 uppercase tracking-widest">Total</span>
                            </div>
                            <div className="mt-4">
                              <div className="text-2xl font-black text-foreground">{msg.data.total_issues || 0}</div>
                              <div className="text-[10px] text-primary font-bold uppercase mt-1">Tâches totales</div>
                            </div>
                          </div>
                        </div>
                      </div>
                    )}

                    {msg.display_type === "gantt" && msg.data && msg.data.issues && (
                      <div className="mt-5 overflow-hidden bg-card rounded-2xl border border-border shadow-2xl">
                        <div className="p-4 bg-primary/10 border-b border-white/5 flex items-center gap-2">
                          <Calendar className="w-4 h-4 text-primary" />
                          <h4 className="text-xs font-black uppercase tracking-widest text-foreground">Chronologie du Projet</h4>
                        </div>
                        <div className="p-5 space-y-4">
                          {msg.data.issues.slice(0, 10).map((issue: any) => (
                            <div key={issue.id} className="space-y-1.5">
                              <div className="flex justify-between text-[10px]">
                                <span className="font-bold text-foreground/80">#{issue.id} {issue.subject}</span>
                                <span className="text-slate-500 font-mono">{issue.start_date || "?"} → {issue.due_date || "?"}</span>
                              </div>
                              <div className="relative h-2 bg-white/5 rounded-full overflow-hidden">
                                <div
                                  className="absolute h-full bg-primary rounded-full"
                                  style={{
                                    width: `${issue.done_ratio || 0}%`,
                                    left: '0%'
                                  }}
                                />
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ))}
            {loading && (
              <div className="flex gap-5 bg-card p-7 rounded-[32px] border border-border animate-pulse">
                <div className="w-10 h-10 bg-primary/20 rounded-xl flex items-center justify-center">
                  <Loader2 className="w-5.5 h-5.5 text-primary animate-spin" />
                </div>
                <div className="flex-1 space-y-4">
                  <div className="h-2.5 bg-muted rounded-full w-28"></div>
                  <div className="space-y-3">
                    <div className="h-2.5 bg-muted rounded-full w-full"></div>
                    <div className="h-2.5 bg-muted rounded-full w-[90%]"></div>
                  </div>
                </div>
              </div>
            )}
            <div ref={scrollRef} className="h-4" />
          </div>
        </ScrollArea>

        {/* Floating Input Bar */}
        <div className="p-2 md:p-4 pt-0 bg-gradient-to-t from-background via-background/90 to-transparent animate-fade-in-up">
          <form
            onSubmit={handleSendMessage}
            className="max-w-5xl mx-auto relative group px-4"
          >
            <div className="absolute -inset-1 bg-gradient-to-r from-primary/20 to-indigo-600/20 rounded-[30px] blur opacity-0 group-focus-within:opacity-100 transition duration-500" />
            <div className="relative flex items-end">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && !e.shiftKey) {
                    e.preventDefault();
                    if (input.trim() && !loading) {
                      handleSendMessage(e as any);
                    }
                  }
                }}
                placeholder={`Poser une question sur ${projectName}...`}
                className="w-full min-h-[48px] max-h-[600px] py-3.5 pl-6 pr-16 bg-card backdrop-blur-2xl border border-border focus:border-primary/40 text-sm rounded-[20px] shadow-[0_20px_50px_rgba(0,0,0,0.1)] transition-all font-sans placeholder:text-foreground placeholder:font-black focus:ring-0 focus:outline-none glow-primary-hover resize-none overflow-y-auto custom-scrollbar leading-relaxed"
                disabled={loading}
                rows={1}
              />
              <Button
                type="submit"
                size="icon"
                className="absolute right-2 bottom-2 h-8 w-8 rounded-[14px] bg-gradient-to-br from-red-600 to-rose-600 hover:scale-105 active:scale-95 transition-all shadow-xl shadow-red-500/20"
                disabled={loading || !input.trim()}
              >
                {loading ? <Loader2 className="w-5 h-5 animate-spin" /> : <Send className="w-5 h-5" />}
              </Button>
            </div>
          </form>
          <div className="text-center mt-2">
            <span className="text-[10px] font-bold text-slate-600 uppercase tracking-[0.3em]">Analyse Par IA & Donneé du Redmine</span>
          </div>
        </div>
      </main>
    </div>
  )
}
